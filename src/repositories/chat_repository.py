"""
聊天会话数据访问层
"""
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, update, delete
from sqlalchemy.orm import joinedload

from models.chat_session import ChatSession, ChatMessage


class ChatRepository:
    """聊天会话仓储"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_session(
        self, 
        user_id: UUID, 
        title: str,
        config: Optional[Dict] = None
    ) -> ChatSession:
        """创建聊天会话"""
        session = ChatSession(
            user_id=user_id,
            title=title,
            config=config or {}
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session
    
    async def get_session(self, session_id: UUID) -> Optional[ChatSession]:
        """获取聊天会话"""
        stmt = select(ChatSession).where(ChatSession.id == session_id).options(
            joinedload(ChatSession.messages)
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()
    
    async def list_user_sessions(
        self, 
        user_id: UUID, 
        page: int = 1, 
        page_size: int = 50
    ) -> List[ChatSession]:
        """获取用户的所有聊天会话"""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def update_session_title(self, session_id: UUID, title: str) -> Optional[ChatSession]:
        """更新会话标题"""
        session = await self.get_session(session_id)
        if not session:
            return None

        session.title = title
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def update_session_config(self, session_id: UUID, config_updates: Dict) -> Optional[ChatSession]:
        """更新会话配置（部分更新）"""
        # 只查询会话本身，不加载消息
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return None

        # 合并配置：保留原有配置，只更新传入的字段
        current_config = session.config or {}
        updated_config = {**current_config, **config_updates}

        session.config = updated_config
        await self.db.commit()
        await self.db.refresh(session)
        return session
    
    async def delete_session(self, session_id: UUID) -> bool:
        """删除聊天会话"""
        # ✅ 修复：只查询会话本身，不加载消息（性能优化）
        # 数据库的 CASCADE DELETE 会自动删除关联消息
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()
        return True

    async def delete_all_user_sessions(self, user_id: UUID) -> int:
        """删除用户的所有聊天会话"""
        from sqlalchemy import delete
        
        # 先统计要删除的数量
        count_stmt = select(ChatSession).where(ChatSession.user_id == user_id)
        result = await self.db.execute(count_stmt)
        sessions = result.scalars().all()
        deleted_count = len(sessions)
        
        # 删除所有会话（CASCADE 会自动删除关联消息）
        delete_stmt = delete(ChatSession).where(ChatSession.user_id == user_id)
        await self.db.execute(delete_stmt)
        await self.db.commit()
        
        return deleted_count
    
    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        mode: Optional[str] = None,
        document_summaries: Optional[list] = None
    ) -> ChatMessage:
        """添加消息到会话"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            thinking=thinking,
            mode=mode,
            document_summaries=document_summaries
        )
        self.db.add(message)
        await self.db.flush()  # ✅ 确保 message.created_at 已生成

        # ✅ 修复：使用 update 语句直接更新，避免加载所有消息（性能优化）
        update_stmt = (
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=message.created_at)
        )
        await self.db.execute(update_stmt)

        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def add_message_with_ownership_check(
        self,
        session_id: UUID,
        user_id: UUID,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        mode: Optional[str] = None,
        document_summaries: Optional[list] = None
    ) -> Optional[ChatMessage]:
        """✅ 原子性地验证会话所有权并添加消息"""
        # 使用子查询验证所有权，避免额外的数据库查询
        stmt = select(ChatSession.id).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        )
        result = await self.db.execute(stmt)
        session_exists = result.scalar_one_or_none()

        if not session_exists:
            return None

        # 会话存在且属于用户，添加消息
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            thinking=thinking,
            mode=mode,
            document_summaries=document_summaries
        )
        self.db.add(message)
        await self.db.flush()  # ✅ 确保 message.created_at 已生成

        # ✅ 修复：使用 update 语句直接更新，避免加载所有消息（性能优化）
        update_stmt = (
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=message.created_at)
        )
        await self.db.execute(update_stmt)

        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_session_messages(self, session_id: UUID) -> List[ChatMessage]:
        """获取会话的所有消息"""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_session_stats(self, session_id: UUID) -> Dict:
        """获取会话统计信息（消息数量和最后一条消息）"""
        # 获取消息数量
        count_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
        count_result = await self.db.execute(count_stmt)
        message_count = count_result.scalar() or 0
        
        # 获取最后一条消息
        last_msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(1)
        )
        last_msg_result = await self.db.execute(last_msg_stmt)
        last_message = last_msg_result.scalar_one_or_none()
        
        return {
            "messageCount": message_count,
            "lastMessage": last_message.content[:50] if last_message else ""
        }

    async def delete_last_assistant_message(
        self,
        session_id: UUID,
        user_id: UUID
    ) -> Optional[str]:
        """
        删除会话中最后一条 AI 回复（原子性验证所有权）
        
        Args:
            session_id: 会话ID
            user_id: 用户ID（用于验证所有权）
            
        Returns:
            被删除的消息ID，如果没有找到则返回 None
        """
        # 先验证会话所有权
        session_stmt = select(ChatSession.id).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        )
        session_result = await self.db.execute(session_stmt)
        if not session_result.scalar_one_or_none():
            return None
        
        # 查找最后一条 assistant 消息
        last_assistant_stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == 'assistant'
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(1)
        )
        result = await self.db.execute(last_assistant_stmt)
        last_assistant_message = result.scalar_one_or_none()
        
        if not last_assistant_message:
            return None
        
        deleted_id = str(last_assistant_message.id)
        
        # 删除该消息
        await self.db.delete(last_assistant_message)
        
        # 更新会话的 updated_at 时间戳
        update_stmt = (
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=datetime.utcnow())
        )
        await self.db.execute(update_stmt)
        
        await self.db.commit()
        
        return deleted_id


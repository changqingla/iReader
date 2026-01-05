"""
压缩管理器

实现上下文压缩算法，包括分割点查找、LLM摘要生成等
"""

from typing import List, Tuple, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from context.models import Message, CompressionRecord, MessageType
from context.session_storage import SessionStorage
from context.token_counter import calculate_tokens
from context.prompts.compression_prompt import (
    build_compression_prompt,
    validate_compression_output,
    extract_summary_content
)
from config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CompressionManager:
    """压缩管理器 - 实现上下文压缩算法"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        storage: Optional[SessionStorage] = None
    ):
        """
        初始化压缩管理器
        
        Args:
            llm: LLM实例，用于生成摘要（必需）
            storage: 会话存储实例，如果为None则创建新实例
        """
        # LLM实例（从外部传入，与当前请求使用的LLM保持一致）
        self.llm = llm
        
        # 存储
        self.storage = storage or SessionStorage()
        
        # 配置参数
        self.settings = get_settings()
        self.preserve_ratio = self.settings.compression_preserve_ratio
    
    # ========================================================================
    # 主要压缩方法
    # ========================================================================
    
    
    def compress_session(self, session_id: str) -> CompressionRecord:
        """
        压缩会话历史
        
        这是主要的压缩入口方法
        
        Args:
            session_id: 会话ID
            
        Returns:
            压缩记录
        """
        logger.info(f"Starting compression for session: {session_id}")
        
        # 获取所有活跃消息
        messages = self.storage.get_messages(session_id, include_compressed=False)
        
        if not messages:
            raise ValueError(f"No messages found for session: {session_id}")
        
        # 执行压缩
        compressed_messages, summary_message, compression_record = self.compress_history(messages)
        
        # 保存结果
        self._save_compression_result(
            session_id=session_id,
            compressed_messages=compressed_messages,
            summary_message=summary_message,
            compression_record=compression_record
        )
        
        logger.info(
            f"Compression completed: session={session_id}, "
            f"compressed={len(compressed_messages)} messages, "
            f"saved={compression_record.saved_tokens} tokens"
        )
        
        return compression_record
    
    def compress_history(
        self,
        messages: List[Message]
    ) -> Tuple[List[Message], Message, CompressionRecord]:
        """
        执行压缩算法
        
        核心逻辑：
        1. 计算每条消息的token数
        2. 从后往前检查，找到即将使累积达到30%的消息
        3. 该消息就是分割点位置，需要确保在对话边界（assistant回答之后）
        4. 分离消息
        5. 调用LLM生成XML摘要
        6. 创建压缩记录
        
        Args:
            messages: 需要压缩的消息列表
            
        Returns:
            (被压缩的消息列表, 摘要消息, 压缩记录)
        """
        # 过滤出活跃消息（排除已压缩的，但保留压缩摘要）
        active_messages = [
            msg for msg in messages
            if not msg.is_compressed or msg.message_type == MessageType.COMPRESSION
        ]
        
        if not active_messages:
            raise ValueError("No active messages to compress")
        
        # ========================================================================
        # 步骤1: 计算总token数
        # ========================================================================
        total_tokens = sum(msg.token_count for msg in active_messages)
        logger.debug(f"Total tokens before compression: {total_tokens}")
        
        # ========================================================================
        # 步骤2: 从后往前检查，找到即将达到30%的位置
        # ========================================================================
        target_preserve_tokens = int(total_tokens * self.preserve_ratio)
        accumulated_tokens = 0
        split_index = None
        
        for i in range(len(active_messages) - 1, -1, -1):
            current_token = active_messages[i].token_count
            
            # 检查：加上当前消息后是否会达到或超过30%
            if accumulated_tokens + current_token >= target_preserve_tokens:
                # 当前消息就是分割点位置，需要确保在对话边界
                if active_messages[i].role == "assistant":
                    # 当前消息是assistant，分割点在其之后
                    split_index = i + 1
                    logger.debug(f"Split point found at assistant message: index={i}")
                    break
                else:
                    # 当前消息是user，向前找最近的assistant
                    for j in range(i - 1, -1, -1):
                        if active_messages[j].role == "assistant":
                            split_index = j + 1
                            logger.debug(f"Split point found at previous assistant: index={j}")
                            break
                    break
            
            # 未达到阈值，继续累积
            accumulated_tokens += current_token
        
        # ========================================================================
        # 步骤3: 验证分割点
        # ========================================================================
        if split_index is None:
            raise ValueError("Could not find valid split point (no assistant message found)")
        
        # 🔧 边界条件处理：如果最后一条消息本身就超过30%
        # split_index >= len(active_messages) 说明从最后一条消息开始累积就已经达到30%
        # 此时应该保留最后一条消息，压缩前面所有
        if split_index >= len(active_messages):
            last_msg_tokens = active_messages[-1].token_count
            split_index = len(active_messages) - 1  # 至少保留最后1条
            logger.warning(
                f"Last message alone ({last_msg_tokens} tokens) exceeds preserve ratio target "
                f"({target_preserve_tokens} tokens). Will preserve it and compress all others. "
                f"Adjusted split_index to {split_index}"
            )
        
        # 最终验证：必须有消息可压缩
        if split_index == 0:
            raise ValueError("Cannot compress: only one message in session")
        
        # ========================================================================
        # 步骤4: 分离消息
        # ========================================================================
        messages_to_compress = active_messages[:split_index]
        messages_to_preserve = active_messages[split_index:]
        
        if not messages_to_compress:
            raise ValueError("No messages to compress")
        
        logger.info(
            f"Messages split: compress={len(messages_to_compress)}, "
            f"preserve={len(messages_to_preserve)}"
        )
        
        # ========================================================================
        # 步骤5: 调用LLM生成XML摘要
        # ========================================================================
        summary_content = self._generate_summary(messages_to_compress)
        # 使用传入的 LLM 的模型名称进行 token 计算
        model_name = getattr(self.llm, 'model_name', getattr(self.llm, 'model', 'gpt-3.5-turbo'))
        summary_tokens = calculate_tokens(summary_content, model_name)
        
        logger.info(f"Summary generated: {summary_tokens} tokens")
        
        # ========================================================================
        # 步骤6: 创建压缩记录和摘要消息
        # ========================================================================
        compressed_tokens = sum(msg.token_count for msg in messages_to_compress)
        compressed_message_ids = [msg.message_id for msg in messages_to_compress]
        
        # 计算当前是第几轮压缩
        session_id = messages_to_compress[0].session_id
        compression_history = self.storage.get_compression_history(session_id)
        current_round = len(compression_history) + 1
        
        # 创建压缩记录
        compression_record = CompressionRecord.create_new(
            session_id=session_id,
            round=current_round,
            original_message_count=len(messages_to_compress),
            compressed_token_count=compressed_tokens,
            summary_token_count=summary_tokens,
            summary_content=summary_content,
            compressed_message_ids=compressed_message_ids
        )
        
        # 创建摘要消息
        # 使用被压缩区间的第一条消息的sequence_number
        # 这样摘要会在正确的位置（被压缩消息的开始位置）
        # 旧的摘要（如果有）会被标记为is_compressed=TRUE，不会冲突
        summary_seq = messages_to_compress[0].sequence_number
        summary_message = Message.create_compression_message(
            session_id=session_id,
            content=summary_content,
            token_count=summary_tokens,
            compression_id=compression_record.compression_id,
            sequence_number=summary_seq
        )
        
        logger.debug(
            f"Summary message created with sequence_number={summary_seq} "
            f"(replacing compressed messages seq={messages_to_compress[0].sequence_number}-{messages_to_compress[-1].sequence_number})"
        )
        
        logger.info(
            f"Compression record created: round={current_round}, "
            f"ratio={compression_record.compression_ratio:.2%}"
        )
        
        return messages_to_compress, summary_message, compression_record
    
    # ========================================================================
    # 私有辅助方法
    # ========================================================================
    
    def _generate_summary(self, messages: List[Message]) -> str:
        """
        调用LLM生成摘要
        
        Args:
            messages: 需要总结的消息列表
            
        Returns:
            XML格式的摘要内容
            
        Raises:
            Exception: LLM调用失败或输出格式不正确
        """
        logger.debug(f"Generating summary for {len(messages)} messages")
        
        # 构建Prompt
        prompt = build_compression_prompt(messages)
        
        # 调用LLM
        response = self.llm.invoke([HumanMessage(content=prompt)])
        output = response.content
        
        # 提取XML内容
        summary = extract_summary_content(output)
        
        # 验证输出格式
        if not validate_compression_output(summary):
            error_msg = f"LLM output does not match expected XML format: {summary[:100]}..."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Summary generated successfully")
        return summary
    
    def _save_compression_result(
        self,
        session_id: str,
        compressed_messages: List[Message],
        summary_message: Message,
        compression_record: CompressionRecord
    ) -> None:
        """
        保存压缩结果
        
        Args:
            session_id: 会话ID
            compressed_messages: 被压缩的消息
            summary_message: 摘要消息
            compression_record: 压缩记录
        """
        # 1. 标记被压缩的消息
        compressed_message_ids = [msg.message_id for msg in compressed_messages]
        self.storage.mark_messages_compressed(
            message_ids=compressed_message_ids,
            compression_id=compression_record.compression_id
        )
        
        # 2. 添加摘要消息
        self.storage.add_message(summary_message)
        
        # 3. 保存压缩记录
        self.storage.save_compression_record(compression_record)
        
        # 4. 更新会话的压缩计数
        self.storage.increment_compression_count(session_id)
        
        # 5. 更新会话token统计（减去被压缩的，加上摘要）
        session = self.storage.get_session(session_id)
        if session:
            new_total = (
                session.total_token_count 
                - compression_record.compressed_token_count 
                + compression_record.summary_token_count
            )
            self.storage.update_session_stats(
                session_id=session_id,
                total_tokens=new_total,
                message_count=session.message_count
            )
        
        logger.info(f"Compression result saved for session: {session_id}")


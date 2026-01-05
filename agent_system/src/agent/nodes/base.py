"""Agent 节点基类和工具方法"""
from typing import Dict, Any, List, Optional, Tuple, TypedDict

from langchain_openai import ChatOpenAI

from ..state import AgentState
from ..thinking import ThoughtGeneratorManager
from ...utils.logger import get_logger
from ...utils.recall_cache import RecallToolCache
from ...tools import RecallTool, WebSearchTool
from ..constants import RECALL_TOOL_CACHE_SIZE

from context.session_manager import SessionManager
from context.context_injector import ContextInjector

logger = get_logger(__name__)


# ============================================================================
# 类型定义
# ============================================================================

class RecallStepInfo(TypedDict):
    """召回步骤信息"""
    index: int
    step: Dict[str, Any]


class StepWithQuery(TypedDict):
    """带查询的步骤信息"""
    index: int
    step: Dict[str, Any]
    query: str
    decision: Optional[Dict[str, Any]]


class BaseAgentNode:
    """节点基类，提供公共功能"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        recall_tool: RecallTool,
        session_manager: SessionManager,
        web_search_tool: Optional[WebSearchTool] = None
    ):
        """
        初始化基础节点
        
        Args:
            llm: 语言模型
            recall_tool: 文档召回工具
            session_manager: 会话管理器
            web_search_tool: 网页搜索工具（可选）
        """
        self.llm = llm
        self.recall_tool = recall_tool
        self.session_manager = session_manager
        self.web_search_tool = web_search_tool
        self.context_injector = ContextInjector()
        self.thought_manager = ThoughtGeneratorManager()
        self._recall_cache = RecallToolCache(max_size=RECALL_TOOL_CACHE_SIZE)
    
    async def _get_conversation_context_async(
        self,
        state: AgentState,
        stage: str = "intent_recognition"
    ) -> str:
        """
        异步获取对话上下文（使用线程池避免阻塞事件循环）
        
        Args:
            state: Agent 状态
            stage: 处理阶段（intent_recognition/planning/answer_generation/simple_interaction）
            
        Returns:
            格式化的对话历史字符串
        """
        import asyncio
        return await asyncio.to_thread(self._get_conversation_context_sync, state, stage)
    
    def _get_conversation_context_sync(
        self,
        state: AgentState,
        stage: str = "intent_recognition"
    ) -> str:
        """
        同步获取对话上下文（内部方法）
        
        Args:
            state: Agent 状态
            stage: 处理阶段
            
        Returns:
            格式化的对话历史字符串
        """
        session_id = state.get('session_id')
        if not session_id:
            return ""
        
        inject_methods = {
            "intent_recognition": self.context_injector.inject_for_intent_recognition,
            "planning": self.context_injector.inject_for_planning,
            "answer_generation": self.context_injector.inject_for_answer_generation,
            "simple_interaction": self.context_injector.inject_for_simple_interaction,
        }
        
        inject_method = inject_methods.get(stage)
        if not inject_method:
            logger.warning(f"Unknown stage: {stage}")
            return ""
        
        messages = inject_method(session_id)
        if not messages:
            return ""
        
        return self.context_injector.format_messages_for_prompt(messages)
    
    def _get_conversation_context(
        self,
        state: AgentState,
        stage: str = "intent_recognition"
    ) -> str:
        """
        同步获取对话上下文（兼容旧代码）
        
        注意：在异步上下文中应使用 _get_conversation_context_async
        """
        return self._get_conversation_context_sync(state, stage)
    
    def _smart_split_document_summaries(
        self,
        document_summaries: Dict[str, str],
        max_tokens: int
    ) -> List[List[Tuple[str, str]]]:
        """
        智能切分文档总结，确保每组在 token 阈值内
        
        Args:
            document_summaries: 文档总结字典 {doc_id: summary}
            max_tokens: Token 阈值
            
        Returns:
            切分后的文档组列表，每组为 [(doc_id, summary), ...]
        """
        from context.token_counter import calculate_tokens
        
        items = list(document_summaries.items())
        total_count = len(items)
        
        logger.info(f"📊 智能切分：{total_count} 个文档总结，阈值 {max_tokens:,} tokens")
        
        all_text = "\n\n".join([summary for _, summary in items])
        total_tokens = calculate_tokens(all_text)
        
        logger.info(f"   总token: {total_tokens:,}")
        
        if total_tokens < max_tokens:
            logger.info(f"   ✅ 无需切分")
            return [items]
        
        logger.info(f"   ⚠️ 超过阈值，开始切分")
        
        def _recursive_split(items_to_split):
            if len(items_to_split) == 1:
                return [items_to_split]
            
            mid = len(items_to_split) // 2
            group1 = items_to_split[:mid]
            group2 = items_to_split[mid:]
            
            group1_text = "\n\n".join([summary for _, summary in group1])
            group2_text = "\n\n".join([summary for _, summary in group2])
            
            group1_tokens = calculate_tokens(group1_text)
            group2_tokens = calculate_tokens(group2_text)
            
            result = []
            
            if group1_tokens < max_tokens:
                result.append(group1)
            else:
                result.extend(_recursive_split(group1))
            
            if group2_tokens < max_tokens:
                result.append(group2)
            else:
                result.extend(_recursive_split(group2))
            
            return result
        
        groups = _recursive_split(items)
        logger.info(f"   ✅ 切分完成：{len(groups)} 组")
        
        return groups
    
    def _build_collected_info_for_answer(self, state: AgentState) -> str:
        """
        构建用于答案生成的信息上下文
        
        支持三种模式：
        1. 文档总结模式：使用 document_summaries
        2. 直接内容模式：使用 direct_content
        3. 召回模式：使用 execution_results
        
        Args:
            state: Agent 状态
            
        Returns:
            收集的信息文本
            
        Raises:
            RuntimeError: 无可用内容时抛出
        """
        use_direct_content = state.get("use_direct_content", False)
        document_summaries = state.get("document_summaries", {})
        
        if document_summaries:
            logger.info(f"📚 使用文档总结生成答案：{len(document_summaries)} 个文档")
            document_names = state.get("document_names", {}) or {}
            
            summary_lines = []
            for i, (doc_id, summary) in enumerate(document_summaries.items(), 1):
                doc_display_name = document_names.get(doc_id, doc_id)
                summary_lines.append(f"## 文档 {i}: {doc_display_name}")
                summary_lines.append(summary)
                summary_lines.append("")
            
            return "\n".join(summary_lines)
        
        elif use_direct_content:
            content = state.get("direct_content", "")
            if not content:
                raise RuntimeError("Direct content mode enabled but no direct_content provided")
            
            logger.info(f"📄 使用直接内容模式，长度: {len(content)} 字符")
            return content
        
        else:
            execution_results = state.get("execution_results", [])
            if not execution_results:
                raise RuntimeError("No execution results found for answer generation")
            
            logger.info(f"📊 使用召回结果生成答案：{len(execution_results)} 个")
            
            recall_lines = []
            for i, result in enumerate(execution_results, 1):
                if result.get("result"):
                    step_title = result.get("step_title", f"步骤 {i}")
                    recall_lines.append(f"## {step_title}\n{result['result']}\n")
            
            return "\n".join(recall_lines)

"""AgentNodes 组合类"""
from typing import Dict, Any, Optional, AsyncGenerator

from langchain_openai import ChatOpenAI

from .document_nodes import DocumentNodes
from .planning_nodes import PlanningNodes
from .execution_nodes import ExecutionNodes
from .answer_nodes import AnswerNodes
from .react_nodes import ReActNodes
from ..state import AgentState
from ...tools import RecallTool, WebSearchTool
from ...utils.logger import get_logger

from context.session_manager import SessionManager

logger = get_logger(__name__)


class AgentNodes:
    """
    Agent 节点组合类
    
    组合所有节点模块，提供统一的接口
    """
    
    def __init__(
        self,
        llm: ChatOpenAI,
        recall_tool: RecallTool,
        session_manager: SessionManager,
        web_search_tool: Optional[WebSearchTool] = None
    ):
        """
        初始化 Agent 节点
        
        Args:
            llm: 语言模型
            recall_tool: 文档召回工具
            session_manager: 会话管理器
            web_search_tool: 网页搜索工具（可选）
        """
        # 初始化各个节点模块
        self._document_nodes = DocumentNodes(llm, recall_tool, session_manager, web_search_tool)
        self._planning_nodes = PlanningNodes(llm, recall_tool, session_manager, web_search_tool)
        self._execution_nodes = ExecutionNodes(llm, recall_tool, session_manager, web_search_tool)
        self._answer_nodes = AnswerNodes(llm, recall_tool, session_manager, web_search_tool)
        self._react_nodes = ReActNodes(llm, recall_tool, session_manager, web_search_tool)
        
        # 保存引用以便访问
        self.llm = llm
        self.recall_tool = recall_tool
        self.session_manager = session_manager
        self.web_search_tool = web_search_tool
        self.thought_manager = self._document_nodes.thought_manager
        
        logger.info("AgentNodes initialized")
    
    # 文档节点
    async def document_check_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._document_nodes.document_check_node_stream(state):
            yield event
    
    # 规划节点
    async def intent_recognition_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._planning_nodes.intent_recognition_node_stream(state):
            yield event
    
    async def strategy_selection_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._planning_nodes.strategy_selection_node_stream(state):
            yield event
    
    async def sub_question_generation_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._planning_nodes.sub_question_generation_node_stream(state):
            yield event
    
    async def plan_generation_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._planning_nodes.plan_generation_node_stream(state):
            yield event
    
    # 执行节点
    async def execution_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._execution_nodes.execution_node_stream(state):
            yield event
    
    # 答案节点
    async def answer_generation_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._answer_nodes.answer_generation_node_stream(state):
            yield event
    
    # ReAct Agent 节点
    async def react_agent_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._react_nodes.react_agent_node_stream(state):
            yield event
    
    async def document_summary_node_stream(self, state: AgentState) -> AsyncGenerator[Dict[str, Any], None]:
        """文档总结节点"""
        async for event in self._document_nodes.document_summary_node_stream(state):
            yield event

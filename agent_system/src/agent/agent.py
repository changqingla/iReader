"""Main agent class for orchestrating the workflow."""
import json
import time
import uuid
from typing import Dict, Any, Optional, List

from langchain_openai import ChatOpenAI

from .state import AgentState, IntentType
from .nodes import AgentNodes
from ..tools import create_recall_tool, create_web_search_tool
from .constants import ESTIMATED_SYSTEM_TOKENS, RESERVED_ANSWER_TOKENS
from ..utils.logger import get_logger
from config import get_settings

# 上下文管理模块 - 强制依赖
from context.session_manager import SessionManager
from context.session_storage import SessionStorage

logger = get_logger(__name__)


# ============================================================================
# Utility Functions for Document ID Processing
# ============================================================================

def normalize_doc_id(doc_id: str) -> str:
    """
    Normalize document ID: only strip whitespace, preserve original case.
    
    Args:
        doc_id: Raw document ID string
        
    Returns:
        Normalized document ID (with whitespace removed)
    """
    return doc_id.strip()  # 只去除空白，保持原始大小写


def parse_and_normalize_doc_ids(doc_ids_str: str) -> List[str]:
    """
    Parse document IDs string and normalize all IDs (strip whitespace only).
    
    Supports two formats:
    1. Comma-separated: "doc1, doc2, doc3"
    2. JSON array: ["doc1", "doc2", "doc3"]
    
    Note: Document IDs preserve their original case. Only leading/trailing 
    whitespace is removed. This ensures IDs match exactly with the database.
    
    Args:
        doc_ids_str: Document IDs string (comma-separated or JSON array)
        
    Returns:
        List of document IDs with whitespace removed (empty list if input is empty)
        
    Raises:
        ValueError: If doc_ids_str is invalid JSON array format
    """
    if not doc_ids_str or not doc_ids_str.strip():
        return []
    
    # Try to parse as JSON array
    if doc_ids_str.strip().startswith('['):
        try:
            doc_ids = json.loads(doc_ids_str)
            if not isinstance(doc_ids, list):
                raise ValueError(f"Expected JSON array, got {type(doc_ids)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON array format for doc_ids: {str(e)}")
    else:
        # Parse as comma-separated string
        doc_ids = [doc_id.strip() for doc_id in doc_ids_str.split(",")]
    
    # Strip whitespace from all IDs and filter out empty strings
    # Note: Original case is preserved for database matching
    processed_ids = [normalize_doc_id(doc_id) for doc_id in doc_ids if doc_id and doc_id.strip()]
    
    return processed_ids


class IntelligentAgent:
    """
    Main intelligent agent for processing user queries.
    
    This agent orchestrates the entire workflow from intent recognition
    to answer generation.
    """
    
    def __init__(self):
        """
        Initialize the intelligent agent with minimal startup dependencies.
        
        Note: LLM, Recall tool, and Web search tool are NOT initialized here.
        They will be created dynamically for each request using configuration
        parameters from the request body. This ensures full dynamic configuration
        without depending on environment variables.
        """
        self.settings = get_settings()
        logger.info("Initializing IntelligentAgent (dynamic configuration mode)...")
        
        # Initialize session manager (the only persistent dependency)
        storage = SessionStorage()
        self.session_manager = SessionManager(storage)
        logger.info("✅ Session manager initialized")
        
        logger.info("✅ IntelligentAgent initialization complete")
        logger.info("📌 LLM, Recall, and Web Search tools will be created per-request")
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a session.
        
        Args:
            session_id: Session ID to retrieve history for
            
        Returns:
            List of message dictionaries
        """
        messages = self.session_manager.get_conversation_history(session_id)
        if not messages:
            return []
        
        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content,
                "type": msg.message_type.value,
                "token_count": msg.token_count,
                "created_at": msg.created_at.isoformat(),
                "is_compressed": msg.is_compressed
            })
        logger.debug(f"Retrieved {len(history)} messages from SessionManager")
        return history
    
    def clear_conversation(self, session_id: str) -> bool:
        """
        清除会话历史（建议创建新会话代替）
        
        注意：此方法不会删除数据库中的历史记录，只是建议用户创建新会话
        """
        logger.info(f"清除会话请求: {session_id}")
        logger.info("建议：创建新会话以获得干净的对话环境")
        return True
    
    async def process_query_stream(
        self,
        show_thinking: bool = True,
        **kwargs
    ):
        """
        Stream-enabled version of process_query with thinking process.
        
        This method yields SSE-compatible events for:
        - Thinking process (<think>...</think>)
        - Answer chunks (token by token)
        - Follow-up questions
        - Node completion events
        
        Args:
            show_thinking: Whether to show thinking process
            **kwargs: Same parameters as process_query()
            
        Yields:
            Dict with 'type' and 'data' keys for SSE events
        """
        start_time = time.time()
        
        # Extract parameters (same as process_query)
        user_query = kwargs.get("user_query")
        mode_type = kwargs.get("mode_type")
        enable_web_search = kwargs.get("enable_web_search")
        session_id = kwargs.get("session_id")
        content = kwargs.get("content")
        document_contents = kwargs.get("document_contents")  # 🔑 新增：多文档内容字典
        document_names = kwargs.get("document_names")  # 🔑 新增：文档名称映射 Dict[doc_id, doc_name]
        kb_id = kwargs.get("kb_id")  # 🔑 新增：知识库ID
        user_id = kwargs.get("user_id")  # 🔑 新增：用户ID
        refresh_summary_cache = kwargs.get("refresh_summary_cache", False)  # 🔑 新增：是否刷新文档总结缓存
        
        # Dynamic configuration
        openai_api_key = kwargs.get("openai_api_key")
        openai_api_base = kwargs.get("openai_api_base")
        model_name = kwargs.get("model_name")
        max_context_tokens = kwargs.get("max_context_tokens")
        search_engine = kwargs.get("search_engine", "tavily")
        search_engine_api_key = kwargs.get("search_engine_api_key")
        
        # Recall configuration
        recall_api_url = kwargs.get("recall_api_url")
        recall_index_names = kwargs.get("recall_index_names")
        recall_doc_ids = kwargs.get("recall_doc_ids", "")
        recall_es_host = kwargs.get("recall_es_host")
        recall_top_n = kwargs.get("recall_top_n")
        recall_similarity_threshold = kwargs.get("recall_similarity_threshold")
        recall_vector_similarity_weight = kwargs.get("recall_vector_similarity_weight")
        recall_model_factory = kwargs.get("recall_model_factory")
        recall_model_name = kwargs.get("recall_model_name")
        recall_model_base_url = kwargs.get("recall_model_base_url")
        recall_api_key = kwargs.get("recall_api_key")
        recall_use_rerank = kwargs.get("recall_use_rerank")
        recall_rerank_factory = kwargs.get("recall_rerank_factory", "")
        recall_rerank_model_name = kwargs.get("recall_rerank_model_name", "")
        recall_rerank_base_url = kwargs.get("recall_rerank_base_url", "")
        recall_rerank_api_key = kwargs.get("recall_rerank_api_key", "")
        
        # Validation (reuse exact logic from process_query)
        required_params = {
            "openai_api_key": openai_api_key,
            "openai_api_base": openai_api_base,
            "model_name": model_name,
            "max_context_tokens": max_context_tokens,
            "recall_api_url": recall_api_url,
            "recall_index_names": recall_index_names,
            "recall_es_host": recall_es_host,
            "recall_top_n": recall_top_n,
            "recall_similarity_threshold": recall_similarity_threshold,
            "recall_vector_similarity_weight": recall_vector_similarity_weight,
            "recall_model_factory": recall_model_factory,
            "recall_model_name": recall_model_name,
            "recall_model_base_url": recall_model_base_url,
            "recall_api_key": recall_api_key,
            "recall_use_rerank": recall_use_rerank,
        }
        
        missing_params = [k for k, v in required_params.items() if v is None]
        if missing_params:
            raise ValueError(f"Missing required configuration parameters: {', '.join(missing_params)}")
        
        if recall_use_rerank:
            rerank_params = {
                "recall_rerank_factory": recall_rerank_factory,
                "recall_rerank_model_name": recall_rerank_model_name,
                "recall_rerank_base_url": recall_rerank_base_url,
                "recall_rerank_api_key": recall_rerank_api_key,
            }
            missing_rerank = [k for k, v in rerank_params.items() if not v or v == ""]
            if missing_rerank:
                raise ValueError(f"Rerank is enabled but missing required parameters: {', '.join(missing_rerank)}")
        
        # Create LLM instance
        runtime_llm = ChatOpenAI(
            model=model_name,
            temperature=self.settings.temperature,
            openai_api_key=openai_api_key,
            openai_api_base=openai_api_base,
            streaming=True  # Enable streaming
        )
        
        # Parse document IDs
        document_ids = parse_and_normalize_doc_ids(recall_doc_ids)
        document_count = len(document_ids)
        
        def parse_recall_index_names(index_names_str: str) -> list:
            if not index_names_str:
                return []
            return [name.strip() for name in index_names_str.split(",")]
        
        # Create tools
        recall_tool_instance = create_recall_tool(
            api_url=recall_api_url,
            index_names=parse_recall_index_names(recall_index_names),
            es_host=recall_es_host,
            model_base_url=recall_model_base_url,
            api_key=recall_api_key,
            doc_ids=document_ids,
            top_n=recall_top_n,
            similarity_threshold=recall_similarity_threshold,
            vector_similarity_weight=recall_vector_similarity_weight,
            model_factory=recall_model_factory,
            model_name=recall_model_name,
            use_rerank=recall_use_rerank,
            rerank_factory=recall_rerank_factory if recall_use_rerank and recall_rerank_factory else None,
            rerank_model_name=recall_rerank_model_name if recall_use_rerank and recall_rerank_model_name else None,
            rerank_base_url=recall_rerank_base_url if recall_use_rerank and recall_rerank_base_url else None,
            rerank_api_key=recall_rerank_api_key if recall_use_rerank and recall_rerank_api_key else None
        )
        
        final_enable_web_search = enable_web_search if enable_web_search is not None else self.settings.enable_web_search
        web_search_tool_instance = None
        if final_enable_web_search and search_engine_api_key:
            web_search_tool_instance = create_web_search_tool(
                api_key=search_engine_api_key,
                search_engine=search_engine,
                max_results=self.settings.search_max_results
            )
            logger.info(f"✅ Created Web Search Tool instance ({search_engine})")
        elif final_enable_web_search and not search_engine_api_key:
            logger.warning("⚠️ Web search is enabled but no search_engine_api_key provided, web search will be unavailable")
        
        # Generate session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())
            logger.info(f"No session_id provided, generated new: {session_id}")
        
        logger.info(f"Processing query [session: {session_id}]: {user_query[:100]}...")
        
        # Session Management (copy from process_query)
        session = self.session_manager.get_or_create_session(session_id=session_id)
        session_id = str(session.session_id)
        session_tokens = session.total_token_count
        
        # Load session history
        session_messages = self.session_manager.get_conversation_history(session_id)
        session_history = session_messages if session_messages else None
        
        if session_messages:
            logger.info(f"Loaded session history: {len(session_messages)} messages, {session_tokens} tokens")
        
        # Calculate available tokens (copy from process_query)
        from context.token_counter import calculate_tokens
        
        query_tokens = calculate_tokens(user_query, model_name)
        used_tokens = session_tokens + query_tokens + ESTIMATED_SYSTEM_TOKENS + RESERVED_ANSWER_TOKENS
        available_tokens = max(0, max_context_tokens - used_tokens)
        
        logger.info("=" * 60)
        logger.info("📊 当前上下文使用情况")
        logger.info("=" * 60)
        logger.info(f"最大上下文: {max_context_tokens:,} tokens")
        logger.info(f"会话历史: {session_tokens:,} tokens (压缩摘要 + 保留消息)")
        logger.info(f"当前问题: {query_tokens:,} tokens")
        logger.info(f"系统提示: {ESTIMATED_SYSTEM_TOKENS:,} tokens (估计)")
        logger.info(f"预留回答: {RESERVED_ANSWER_TOKENS:,} tokens")
        if max_context_tokens > 0:
            logger.info(f"已使用: {used_tokens:,} tokens ({(used_tokens/max_context_tokens)*100:.1f}%)")
            logger.info(f"剩余可用: {available_tokens:,} tokens ({(available_tokens/max_context_tokens)*100:.1f}%)")
        else:
            logger.warning(f"⚠️ max_context_tokens is {max_context_tokens}, cannot calculate percentage")
            logger.info(f"已使用: {used_tokens:,} tokens")
            logger.info(f"剩余可用: {available_tokens:,} tokens")
        logger.info("=" * 60)
        
        # ========================================================================
        # 🔑 文档处理模式判断逻辑
        # 
        # 策略选择由 strategy_selection_node 根据 doc_count 和 intent 决定：
        # - 单文档 + 内容小 → full_content（直接使用完整内容）
        # - 多文档 + 总结/综述 → multi_doc_summary（使用预加载的完整内容）
        # - 其他情况 → chunk_recall（分块召回）
        # ========================================================================
        use_direct_content_mode = False
        direct_content_value = None
        content_tokens = None
        
        logger.info("=" * 60)
        logger.info("📊 文档处理模式判断 [流式接口]")
        logger.info("=" * 60)
        logger.info("🔍 判断参数:")
        logger.info(f"   - content 是否提供: {'是' if content else '否'} (长度: {len(content) if content else 0})")
        logger.info(f"   - document_contents 是否提供: {'是' if document_contents else '否'} (数量: {len(document_contents) if document_contents else 0})")
        logger.info(f"   - document_ids 数量: {document_count}")
        logger.info(f"   - document_ids: {document_ids}")
        
        # 多文档场景：后续策略由 strategy_selection_node 决定
        # - 文献总结/综述生成 → multi_doc_summary（使用 document_contents 完整内容）
        # - 论文评审/文献问答 → chunk_recall（分块召回）
        if document_count > 1:
            logger.info("✅ 多文档场景")
            logger.info(f"   文档数量: {document_count} 篇")
            logger.info("   策略将由 strategy_selection_node 根据意图类型决定：")
            logger.info("   - 文献总结/综述生成 → multi_doc_summary（完整内容）")
            logger.info("   - 论文评审/文献问答 → chunk_recall（分块召回）")
            if content:
                logger.info("   ⚠️ 忽略 content 参数（多文档场景使用 document_contents）")
            logger.info("=" * 60)
        
        # 判断2：单文档或无文档，检查是否可以使用直接内容模式
        else:
            if content:
                from ..utils import should_use_direct_content
                
                should_use, token_count = should_use_direct_content(
                    content=content,
                    available_tokens=available_tokens,
                    threshold=self.settings.direct_content_threshold,
                    model=model_name
                )
                content_tokens = token_count
                
                if should_use:
                    # ✅ 直接内容模式
                    use_direct_content_mode = True
                    direct_content_value = content
                    logger.info("✅ 模式：直接内容模式")
                    logger.info("   原因：单文档 + content 未超阈值")
                    logger.info(f"   文档 Token 数: {token_count:,}")
                    logger.info(f"   可用 Token 数: {available_tokens:,}")
                    if available_tokens > 0:
                        logger.info(f"   使用比例: {(token_count/available_tokens)*100:.1f}%")
                    logger.info(f"   文档数量: {document_count}")
                    logger.info("=" * 60)
                else:
                    # content 超阈值，使用召回
                    logger.info("✅ 模式：传统召回模式（混合召回）")
                    logger.info("   原因：content 超阈值")
                    logger.info(f"   文档 Token 数: {token_count:,}")
                    logger.info(f"   阈值: {int(available_tokens * self.settings.direct_content_threshold):,}")
                    logger.info(f"   文档数量: {document_count}")
                    logger.info("=" * 60)
            else:
                # 没有 content，使用召回
                logger.info("✅ 模式：传统召回模式（混合召回）")
                logger.info("   原因：未提供 content")
                logger.info(f"   文档数量: {document_count}")
                logger.info("=" * 60)
        
        # 创建 Agent 节点（传入共享的 session_manager）
        agent_nodes = AgentNodes(
            llm=runtime_llm,
            recall_tool=recall_tool_instance,
            session_manager=self.session_manager,
            web_search_tool=web_search_tool_instance
        )
        
        # Reset all thought generators' step counters for this request
        agent_nodes.thought_manager.reset_all_counters()
        
        state: AgentState = {
            "user_query": user_query,
            "mode_type": IntentType(mode_type) if mode_type else None,
            "enable_web_search": final_enable_web_search,
            "document_ids": document_ids,
            "direct_content": direct_content_value,
            "use_direct_content": use_direct_content_mode,
            "content_token_count": content_tokens,
            "document_contents": document_contents,  # 🔑 新增：多文档内容字典
            "document_names": document_names,  # 🔑 新增：文档名称映射 Dict[doc_id, doc_name]
            "kb_id": kb_id,  # 🔑 新增：知识库ID（供内部加载文档）
            "user_id": user_id,  # 🔑 新增：用户ID（供内部加载文档）
            "refresh_summary_cache": refresh_summary_cache,  # 🔑 新增：是否刷新文档总结缓存
            "available_tokens": available_tokens,
            "strategy": None,
            "sub_questions": None,
            "detected_intent": None,
            "plan": None,
            "current_step_index": 0,
            "execution_results": [],
            "final_answer": "",
            "follow_up_questions": None,
            "messages": [],
            "session_id": session_id,
            "session_history": session_history,  # Added
            "session_tokens": session_tokens,  # Added
            "_user_message_saved": False,
            "max_context_tokens": max_context_tokens,
            "compression_threshold": int(max_context_tokens * 0.8),  # Added
            "start_time": start_time,
            "error": None
        }
        
        # Start thinking stream
        if show_thinking:
            yield {
                "type": "thinking_start",
                "data": {"content": "<think>\n"}
            }
        
        # Execute workflow with streaming
        try:
            # Document Check
            async for event in agent_nodes.document_check_node_stream(state):
                if event["type"] == "thought_chunk":
                    if show_thinking:
                        yield {"type": "thought_chunk", "data": {"content": event["content"]}}
                elif event["type"] == "node_complete":
                    state.update(event["data"])
                elif event["type"] == "node_error":
                    logger.error(f"Node error in document_check: {event.get('error')}")
                    yield {"type": "error", "data": {"message": f"Document check failed: {event.get('error')}"}}
                    return
            
            # Intent Recognition
            async for event in agent_nodes.intent_recognition_node_stream(state):
                if event["type"] == "thought_chunk":
                    if show_thinking:
                        yield {"type": "thought_chunk", "data": {"content": event["content"]}}
                elif event["type"] == "node_complete":
                    state.update(event["data"])
                elif event["type"] == "node_error":
                    logger.error(f"Node error in intent_recognition: {event.get('error')}")
                    yield {"type": "error", "data": {"message": f"Intent recognition failed: {event.get('error')}"}}
                    return
            
            # 🔀 路由分发：根据 route 字段决定走 Pipeline 还是 ReAct
            route = state.get("route", "pipeline")
            
            if route == "react":
                # ReAct Agent 路线
                logger.info("🤖 路由到 ReAct Agent")
                
                # End thinking (ReAct 会输出自己的思考过程)
                if show_thinking:
                    yield {"type": "thinking_end", "data": {"content": "</think>\n\n"}}
                
                # 执行 ReAct Agent
                async for event in agent_nodes.react_agent_node_stream(state):
                    if event["type"] == "thought_chunk":
                        yield {"type": "thought_chunk", "data": {"content": event["data"]["content"]}}
                    elif event["type"] == "answer_chunk":
                        yield {"type": "answer_chunk", "data": {"content": event["data"]["content"]}}
                    elif event["type"] == "node_complete":
                        state.update(event["data"])
                    elif event["type"] == "node_error":
                        logger.error(f"Node error in react_agent: {event.get('error')}")
                        yield {"type": "error", "data": {"message": f"ReAct agent failed: {event.get('error')}"}}
                        return
                
                # Return final result
                yield {
                    "type": "final_answer",
                    "data": {
                        "answer": state["final_answer"],
                        "session_id": session_id,
                        "detected_intent": str(state.get("detected_intent")),
                        "route": "react"
                    }
                }
                return
            
            # Pipeline 路线继续执行
            logger.info("📋 路由到 Pipeline")
            
            # Strategy Selection
            async for event in agent_nodes.strategy_selection_node_stream(state):
                if event["type"] == "thought_chunk":
                    if show_thinking:
                        yield {"type": "thought_chunk", "data": {"content": event["content"]}}
                elif event["type"] == "node_complete":
                    state.update(event["data"])
                elif event["type"] == "node_error":
                    logger.error(f"Node error in strategy_selection: {event.get('error')}")
                    yield {"type": "error", "data": {"message": f"Strategy selection failed: {event.get('error')}"}}
                    return
            
            strategy = state.get("strategy")

            if strategy == "full_content":
                # Skip to answer_generation directly (no analysis needed)
                logger.info("🚀 Full content mode: skipping to answer generation")
            elif strategy == "multi_doc_summary":
                # Multi-document summary mode: execute document_summary node
                refresh_cache = state.get("refresh_summary_cache", False)
                logger.info("=" * 60)
                logger.info("📚 Multi-document summary mode: generating document summaries")
                logger.info(f"   - 文档数量: {state.get('doc_count', 0)}")
                logger.info(f"   - 强制刷新缓存: {refresh_cache}")
                logger.info("=" * 60)
                
                async for event in agent_nodes.document_summary_node_stream(state):
                    if event["type"] == "thought_chunk":
                        if show_thinking:
                            yield {"type": "thought_chunk", "data": {"content": event["content"]}}
                    elif event["type"] == "node_complete":
                        state.update(event["data"])
                    elif event["type"] == "node_error":
                        logger.error(f"Node error in document_summary: {event.get('error')}")
                        yield {"type": "error", "data": {"message": f"Document summary failed: {event.get('error')}"}}
                        return
                    # 🔑 Forward document summary progress events to frontend
                    elif event["type"] in ("doc_summary_init", "doc_summary_start", "doc_summary_chunk", "doc_summary_complete", "doc_summary_error"):
                        yield {"type": event["type"], "data": event.get("data", {})}
            else:
                # Chunk recall path with replan loop
                detected_intent = state.get("detected_intent")

                # Generate sub-questions for chunk_recall tasks
                logger.info("🎯 Generating sub-questions for chunk_recall task")

                # Sub-question Generation
                async for event in agent_nodes.sub_question_generation_node_stream(state):
                    if event["type"] == "thought_chunk":
                        if show_thinking:
                            yield {"type": "thought_chunk", "data": {"content": event["content"]}}
                    elif event["type"] == "node_complete":
                        state.update(event["data"])
                    elif event["type"] == "node_error":
                        logger.error(f"Node error in sub_question_generation: {event.get('error')}")
                        yield {"type": "error", "data": {"message": f"Sub-question generation failed: {event.get('error')}"}}
                        return
                
                # Plan Generation
                async for event in agent_nodes.plan_generation_node_stream(state):
                    if event["type"] == "thought_chunk":
                        if show_thinking:
                            yield {"type": "thought_chunk", "data": {"content": event["content"]}}
                    elif event["type"] == "node_complete":
                        state.update(event["data"])
                    elif event["type"] == "node_error":
                        logger.error(f"Node error in plan_generation: {event.get('error')}")
                        yield {"type": "error", "data": {"message": f"Plan generation failed: {event.get('error')}"}}
                        return

                # Execution Loop with protection
                plan = state.get("plan", {})
                total_steps = len(plan.get("steps", []))
                max_iterations = total_steps * 2  # Protection against infinite loop
                iteration_count = 0

                while state.get("current_step_index", 0) < total_steps:
                    iteration_count += 1
                    if iteration_count > max_iterations:
                        logger.error(f"❌ Execution loop exceeded max iterations ({max_iterations})")
                        if show_thinking:
                            yield {
                                "type": "thought_chunk",
                                "data": {"content": "⚠️ 执行步骤超过最大迭代次数，强制退出循环\n\n"}
                            }
                        break

                    prev_index = state.get("current_step_index", 0)

                    async for event in agent_nodes.execution_node_stream(state):
                        if event["type"] == "thought_chunk":
                            if show_thinking:
                                yield {"type": "thought_chunk", "data": {"content": event["content"]}}
                        elif event["type"] == "node_complete":
                            state.update(event["data"])
                        elif event["type"] == "node_error":
                            logger.error(f"Node error in execution: {event.get('error')}")
                            yield {"type": "error", "data": {"message": f"Execution failed: {event.get('error')}"}}
                            return

                    # Verify current_step_index was updated
                    new_index = state.get("current_step_index", 0)
                    if new_index <= prev_index:
                        logger.warning(f"⚠️ current_step_index not updated: {prev_index} -> {new_index}, forcing increment")
                        state["current_step_index"] = prev_index + 1

                # All execution steps completed
                logger.info("✅ All execution steps completed")
            
            # End thinking
            if show_thinking:
                yield {"type": "thinking_end", "data": {"content": "</think>\n\n"}}
            
            # Answer Generation (stream)
            async for event in agent_nodes.answer_generation_node_stream(state):
                if event["type"] == "answer_chunk":
                    yield {"type": "answer_chunk", "data": {"content": event["content"]}}
                elif event["type"] == "node_complete":
                    state.update(event["data"])
                elif event["type"] == "node_error":
                    logger.error(f"Node error in answer_generation: {event.get('error')}")
                    yield {"type": "error", "data": {"message": f"Answer generation failed: {event.get('error')}"}}
                    return
            
            # Final result
            yield {
                "type": "final_answer",
                "data": {
                    "answer": state["final_answer"],
                    "session_id": session_id,
                    "follow_up_questions": None,  # 已移除猜你想问功能
                    "detected_intent": str(state.get("detected_intent")),
                    "strategy": state.get("strategy")
                }
            }
            
        except Exception as e:
            logger.error(f"Error in streaming query: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "data": {
                    "message": str(e),
                    "session_id": session_id if 'session_id' in locals() else None
                }
            }


def create_agent() -> IntelligentAgent:
    """
    Factory function to create an IntelligentAgent instance.
    
    The agent uses minimal startup initialization (only session manager).
    LLM, Recall, and Web Search tools are created dynamically per-request
    using configuration parameters from the request body.
    
    Returns:
        IntelligentAgent instance ready to process queries
    """
    return IntelligentAgent()


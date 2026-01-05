"""ReAct Agent 节点"""
import asyncio
from typing import Dict, Any, AsyncGenerator, Optional, List, TYPE_CHECKING

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from .base import BaseAgentNode
from ..state import AgentState
from ..react import (
    ReActConfig, 
    Scratchpad, 
    ScratchpadEntry, 
    ActionParser,
    create_default_hook_manager,
    HookAction,
    CompletionDetector,
    CompletionReason,
)
from ...prompts import REACT_AGENT_PROMPT
from ...utils.logger import get_logger
from ...tools.registry import get_tool_registry

if TYPE_CHECKING:
    from ...mcp.tool_adapter import MCPToolAdapter

logger = get_logger(__name__)


class ReActNodes(BaseAgentNode):
    """ReAct Agent 节点 - 支持 Hook 机制和智能完成检测"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = ReActConfig()
        
        # 动态更新可用工具列表（包含 MCP 工具）
        self._update_available_tools()
        
        self.action_parser = ActionParser(self.config)
        
        # 初始化 Hook 管理器
        self.hook_manager = create_default_hook_manager() if self.config.enable_hooks else None
        
        # 初始化完成检测器
        self.completion_detector = CompletionDetector(self.config) if self.config.enable_completion_detection else None
    
    def _update_available_tools(self) -> None:
        """动态更新可用工具列表，包含 MCP 工具"""
        # 基础工具
        tools = ["recall", "web_search"]
        
        # 添加 MCP 工具
        registry = get_tool_registry()
        for tool in registry.get_mcp_tools():
            tools.append(tool.name)
        
        # finish 始终在最后
        tools.append("finish")
        
        # 更新配置
        self.config.available_tools = tuple(tools)
        logger.info(f"📌 ReAct 可用工具: {', '.join(tools)}")
    
    def _get_available_tools_description(self) -> str:
        """
        获取所有可用工具的描述，用于 ReAct prompt
        
        Returns:
            格式化的工具描述字符串
        """
        tools_desc = []
        
        # 1. 内置工具
        tools_desc.append('1. **recall(query)**: Search the user\'s document library for relevant information. Use this when you need to find specific content from uploaded documents.')
        tools_desc.append('2. **web_search(query)**: Search the internet for external information. Use this when you need up-to-date information or knowledge not in the documents.')
        
        # 2. MCP 工具（从 ToolRegistry 获取）
        registry = get_tool_registry()
        mcp_tools = registry.get_mcp_tools()
        
        tool_num = 3  # 从 3 开始编号（1 和 2 是内置工具）
        for tool in mcp_tools:
            # 格式化工具描述
            tool_desc = f'{tool_num}. **{tool.name}(...)**: {tool.description}'
            tools_desc.append(tool_desc)
            tool_num += 1
        
        # 3. finish 工具（始终最后）
        tools_desc.append(f'{tool_num}. **finish(answer)**: Complete the task and provide the final answer. Use this when you have gathered enough information to answer the user\'s question.')
        
        return '\n'.join(tools_desc)
    
    def _get_available_tool_names(self) -> List[str]:
        """
        获取所有可用工具的名称列表
        
        Returns:
            工具名称列表
        """
        tool_names = ['recall', 'web_search']
        
        # 添加 MCP 工具名称
        registry = get_tool_registry()
        for tool in registry.get_mcp_tools():
            tool_names.append(tool.name)
        
        tool_names.append('finish')
        return tool_names
    
    async def react_agent_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        ReAct Agent 主循环
        
        执行 Thought → Action → Observation 循环，直到：
        1. Agent 调用 finish 工具
        2. 达到最大迭代次数
        3. 智能检测到应该结束
        4. 发生错误
        
        Args:
            state: Agent 状态
            
        Yields:
            流式事件字典
        """
        try:
            user_query = state["user_query"]
            session_id = state.get("session_id")
            document_ids = state.get("document_ids", [])
            
            # 初始化 scratchpad
            scratchpad = Scratchpad(
                max_tokens=self.config.max_scratchpad_tokens,
                model=self.llm.model_name if hasattr(self.llm, 'model_name') else "gpt-4"
            )
            
            # 获取对话历史
            context_str = await self._get_conversation_context_async(state, stage="simple_interaction")
            
            # 构建文档信息
            document_info = self._build_document_info(state)
            
            iteration = 0
            final_answer = ""
            
            while iteration < self.config.max_iterations:
                iteration += 1
                logger.info(f"🔄 ReAct 迭代 {iteration}/{self.config.max_iterations}")
                
                # 智能完成检测（优化 5）
                if self.completion_detector and iteration > 1:
                    completion_result = self.completion_detector.check(scratchpad, user_query)
                    if completion_result.should_finish:
                        logger.info(f"🎯 智能检测建议结束: {completion_result.reason.value}")
                        # 完成检测提示只记录日志，不输出到前端
                        # 对于某些原因，强制结束
                        if completion_result.reason in (
                            CompletionReason.STUCK_IN_LOOP,
                            CompletionReason.MAX_ERRORS,
                            CompletionReason.TOKEN_LIMIT
                        ):
                            final_answer = self._generate_forced_answer(scratchpad, user_query)
                            break
                
                # 构建 prompt（包含动态工具列表和当前日期）
                available_tools = self._get_available_tools_description()
                tool_names = ', '.join(self._get_available_tool_names())
                
                # 获取当前日期（北京时间）
                from datetime import datetime, timezone, timedelta
                beijing_tz = timezone(timedelta(hours=8))
                current_date = datetime.now(beijing_tz).strftime("%Y-%m-%d")
                
                prompt = REACT_AGENT_PROMPT.format(
                    user_query=user_query,
                    conversation_history=context_str if context_str else "无历史对话",
                    document_info=document_info,
                    scratchpad=scratchpad.to_string() if len(scratchpad) > 0 else "（首次思考，无历史记录）",
                    available_tools=available_tools,
                    tool_names=tool_names,
                    current_date=current_date
                )
                
                # 调用 LLM - 流式输出思考过程和最终答案
                # 关键改进：
                # 1. 思考过程输出到 thought_chunk
                # 2. 使用 find 而不是 rfind，确保只处理第一个 finish
                # 3. 一旦检测到 finish，只输出该 finish 的答案，忽略后续内容
                llm_output = ""
                thought_output_started = False  # 是否已开始输出思考内容
                thought_output_pos = 0  # 思考内容已输出到的位置
                answer_streaming = False  # 是否在输出最终答案
                answer_output_started = False  # 是否已开始输出答案
                answer_output_pos = 0  # 答案已输出到的位置
                first_finish_pos = -1  # 第一个 finish 的位置（一旦确定就不变）
                first_action_input_pos = -1  # 第一个 finish 对应的 action input 位置
                
                async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    llm_output += chunk_content
                    llm_lower = llm_output.lower()
                    
                    # 检查是否进入答案输出阶段（检测到第一个 finish 动作）
                    # 关键：使用 find 而不是 rfind，只处理第一个 finish
                    if not answer_streaming:
                        for finish_marker in ["action: finish", "action:finish"]:
                            pos = llm_lower.find(finish_marker)
                            if pos != -1:
                                # 检查 finish 后面是否有 action input
                                remaining = llm_lower[pos:]
                                if "action input:" in remaining or "action_input:" in remaining:
                                    answer_streaming = True
                                    first_finish_pos = pos
                                    break
                    
                    # 如果已经在输出答案阶段
                    if answer_streaming:
                        # 使用已记录的第一个 finish 位置
                        if first_finish_pos == -1:
                            continue
                        
                        # 如果还没找到 action input 位置，现在找
                        if first_action_input_pos == -1:
                            for marker in ["action input:", "action_input:"]:
                                marker_pos = llm_lower.find(marker, first_finish_pos)
                                if marker_pos != -1:
                                    first_action_input_pos = marker_pos + len(marker)
                                    # 跳过空白
                                    while first_action_input_pos < len(llm_output) and llm_output[first_action_input_pos] in ' \t\n':
                                        first_action_input_pos += 1
                                    break
                        
                        if first_action_input_pos == -1:
                            continue
                        
                        # 确定答案的结束位置（遇到下一个 Thought: 或 Action: 就停止）
                        answer_end = len(llm_output)
                        for stop_marker in ["\nthought:", "\naction:", "\nobservation:"]:
                            stop_pos = llm_lower.find(stop_marker, first_action_input_pos)
                            if stop_pos != -1 and stop_pos < answer_end:
                                answer_end = stop_pos
                        
                        # 输出新增的答案内容
                        if not answer_output_started:
                            answer_output_pos = first_action_input_pos
                            answer_output_started = True
                        
                        # 只输出到答案结束位置
                        if answer_end > answer_output_pos:
                            new_content = llm_output[answer_output_pos:answer_end]
                            if new_content:
                                yield {"type": "answer_chunk", "data": {"content": new_content}}
                            answer_output_pos = answer_end
                        continue
                    
                    # 流式输出思考部分（只在非 finish 阶段）
                    # 检查是否遇到 Action: 标记
                    action_pos = -1
                    for marker in ["\naction:", "\nAction:", "\nACTION:"]:
                        pos = llm_lower.find(marker.lower())
                        if pos != -1:
                            action_pos = pos
                            break
                    
                    # 确定思考内容的起始位置（跳过 Thought: 前缀）
                    if not thought_output_started:
                        thought_start = 0
                        for prefix in ["thought:", "Thought:", "THOUGHT:", "思考:"]:
                            prefix_lower = prefix.lower()
                            if llm_lower.strip().startswith(prefix_lower):
                                prefix_pos = llm_lower.find(prefix_lower)
                                thought_start = prefix_pos + len(prefix)
                                # 跳过前缀后的空白
                                while thought_start < len(llm_output) and llm_output[thought_start] in ' \t':
                                    thought_start += 1
                                break
                        
                        # 只有当我们确定了前缀位置后才开始输出
                        if thought_start > 0 or len(llm_output) > 20:
                            thought_output_started = True
                            thought_output_pos = thought_start
                    
                    if thought_output_started:
                        # 确定本次输出的结束位置
                        end_pos = action_pos if action_pos != -1 else len(llm_output)
                        
                        # 输出新增的思考内容
                        if end_pos > thought_output_pos:
                            new_content = llm_output[thought_output_pos:end_pos]
                            if new_content:
                                yield {
                                    "type": "thought_chunk",
                                    "data": {
                                        "content": new_content,
                                        "phase": "thinking"
                                    }
                                }
                            thought_output_pos = end_pos
                
                # 思考部分结束，添加换行（只在非 finish 情况下）
                if not answer_streaming:
                    yield {
                        "type": "thought_chunk",
                        "data": {
                            "content": "\n\n",
                            "phase": "thinking"
                        }
                    }
                
                # 解析完整输出获取 Action
                parsed = self.action_parser.parse(llm_output)
                
                # 处理无效 Action
                if not parsed.is_valid:
                    logger.warning(f"⚠️ 无效 Action: {parsed.error_message}")
                    observation = f"[ERROR] {parsed.error_message}"
                    
                    # 添加到 scratchpad
                    entry = ScratchpadEntry(
                        thought=parsed.thought or "（解析失败）",
                        action=parsed.action or "unknown",
                        action_input=parsed.action_input or "",
                        observation=observation
                    )
                    scratchpad.add_entry(entry)
                    
                    # 错误信息只记录日志，不输出到前端
                    continue
                
                # 检查是否是 finish
                if self.action_parser.is_finish_action(parsed):
                    final_answer = self.action_parser.extract_final_answer(parsed)
                    logger.info(f"✅ ReAct 完成，迭代次数: {iteration}")
                    break
                
                # Hook 前处理
                action = parsed.action
                action_input = parsed.action_input
                
                if self.hook_manager:
                    action, action_input, skip_message = await self.hook_manager.run_pre_hooks(
                        action, action_input, state
                    )
                    if skip_message:
                        logger.info(f"⏭️ Hook 跳过工具调用: {skip_message}")
                        observation = f"[SKIPPED] {skip_message}"
                        entry = ScratchpadEntry(
                            thought=parsed.thought,
                            action=action,
                            action_input=action_input,
                            observation=observation
                        )
                        scratchpad.add_entry(entry)
                        # 跳过信息只记录日志，不输出到前端
                        continue
                
                # 执行工具（不输出动作信息到前端）
                observation = await self._execute_tool(action, action_input, state)
                
                # Hook 后处理（优化 1）
                if self.hook_manager:
                    observation = await self.hook_manager.run_post_hooks(
                        action, action_input, observation, state
                    )
                
                # 添加到 scratchpad
                entry = ScratchpadEntry(
                    thought=parsed.thought,
                    action=action,
                    action_input=action_input,
                    observation=observation
                )
                scratchpad.add_entry(entry)
                # 观察结果和统计信息只记录日志，不输出到前端
            
            # 如果达到最大迭代次数但没有 finish
            if not final_answer:
                logger.warning(f"⚠️ ReAct 达到最大迭代次数 {self.config.max_iterations}，强制结束")
                final_answer = self._generate_forced_answer(scratchpad, user_query)
                # 最大迭代提示只记录日志，不输出到前端
                # 强制生成的答案需要流式输出
                for chunk in self._chunk_text(final_answer, chunk_size=50):
                    yield {"type": "answer_chunk", "data": {"content": chunk}}
            
            # 保存会话
            if session_id:
                model_name = self.llm.model_name if hasattr(self.llm, 'model_name') else "unknown"
                
                if not state.get("_user_message_saved"):
                    await asyncio.to_thread(
                        self.session_manager.add_user_message,
                        session_id=session_id,
                        content=user_query,
                        model_name=model_name
                    )
                
                await asyncio.to_thread(
                    self.session_manager.add_assistant_message,
                    session_id=session_id,
                    content=final_answer,
                    model_name=model_name
                )
            
            # 注意：最终答案已在 LLM 流式输出时输出，这里不再重复输出
            
            # 返回结果
            result = {
                "final_answer": final_answer,
                "react_iteration": iteration,
                "messages": state.get("messages", []) + [AIMessage(content=final_answer)]
            }
            
            yield {"type": "node_complete", "data": result}
            
        except Exception as e:
            logger.error(f"Error in react_agent_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "react_agent", "error": str(e)}
    
    def _build_document_info(self, state: AgentState) -> str:
        """构建文档信息字符串"""
        document_ids = state.get("document_ids", [])
        document_names = state.get("document_names", {}) or {}
        
        if not document_ids:
            return "无关联文档"
        
        lines = [f"共 {len(document_ids)} 个文档:"]
        for doc_id in document_ids:
            doc_name = document_names.get(doc_id, doc_id)
            lines.append(f"  - {doc_name}")
        
        return "\n".join(lines)
    
    async def _execute_tool(
        self,
        action: str,
        action_input: str,
        state: AgentState
    ) -> str:
        """
        执行工具调用
        
        支持三种类型的工具：
        1. 内置工具（recall, web_search）
        2. MCP 工具（通过 ToolRegistry 注册）
        3. 未知工具（返回错误）
        
        Args:
            action: 工具名称
            action_input: 工具输入
            state: Agent 状态
            
        Returns:
            工具执行结果（Observation）
        """
        try:
            # 1. 检查内置工具
            if action == "recall":
                return await self._execute_recall(action_input, state)
            elif action == "web_search":
                return await self._execute_web_search(action_input)
            
            # 2. 检查 MCP 工具（通过 ToolRegistry）
            registry = get_tool_registry()
            if registry.has_tool(action):
                return await self._execute_mcp_tool(action, action_input)
            
            # 3. 未知工具
            return f"[ERROR] Unknown tool: {action}"
        except asyncio.TimeoutError:
            return f"[ERROR] Tool execution timed out after {self.config.tool_timeout}s"
        except Exception as e:
            logger.error(f"Tool execution error: {str(e)}", exc_info=True)
            return f"[ERROR] Tool execution failed: {str(e)}"
    
    async def _execute_mcp_tool(self, tool_name: str, tool_input: str) -> str:
        """
        执行 MCP 工具调用
        
        Args:
            tool_name: MCP 工具名称
            tool_input: 工具输入（字符串，将被解析为参数）
            
        Returns:
            工具执行结果
        """
        try:
            registry = get_tool_registry()
            tool = registry.get_tool(tool_name)
            
            if tool is None:
                return f"[ERROR] MCP tool '{tool_name}' not found"
            
            # 解析输入参数
            # MCP 工具可能需要 JSON 格式的输入，或者简单字符串
            import json
            try:
                # 尝试解析为 JSON
                if tool_input.strip().startswith('{'):
                    kwargs = json.loads(tool_input)
                else:
                    # 对于简单字符串输入，尝试推断参数名
                    # 大多数搜索类工具使用 'query' 作为主要参数
                    kwargs = {"query": tool_input}
            except json.JSONDecodeError:
                # 如果 JSON 解析失败，使用原始字符串
                kwargs = {"query": tool_input}
            
            logger.info(f"🔧 执行 MCP 工具: {tool_name}, 参数: {kwargs}")
            
            # 执行工具（带超时）
            result = await asyncio.wait_for(
                tool._arun(**kwargs),
                timeout=self.config.tool_timeout
            )
            
            if not result or result.strip() == "":
                return f"MCP tool '{tool_name}' returned no results."
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"MCP tool '{tool_name}' timed out")
            return f"[ERROR] MCP tool '{tool_name}' timed out after {self.config.tool_timeout}s"
        except Exception as e:
            logger.error(f"MCP tool '{tool_name}' error: {str(e)}", exc_info=True)
            return f"[ERROR] MCP tool '{tool_name}' failed: {str(e)}"
    
    async def _execute_recall(self, query: str, state: AgentState) -> str:
        """执行文档召回"""
        try:
            # 使用现有的 recall_tool
            result = await asyncio.wait_for(
                asyncio.to_thread(self.recall_tool._run, query),
                timeout=self.config.tool_timeout
            )
            
            if not result or result.strip() == "":
                return "未找到相关文档内容。"
            
            return result
        except Exception as e:
            logger.error(f"Recall error: {str(e)}")
            return f"[ERROR] 文档召回失败: {str(e)}"
    
    async def _execute_web_search(self, query: str) -> str:
        """执行网络搜索"""
        if not self.web_search_tool:
            return "[ERROR] 网络搜索功能未启用。"
        
        try:
            result = await asyncio.wait_for(
                self.web_search_tool._arun(query),
                timeout=self.config.tool_timeout
            )
            
            if not result or result.strip() == "":
                return "未找到相关搜索结果。"
            
            return result
        except Exception as e:
            logger.error(f"Web search error: {str(e)}")
            return f"[ERROR] 网络搜索失败: {str(e)}"
    
    def _generate_forced_answer(self, scratchpad: Scratchpad, user_query: str) -> str:
        """当达到最大迭代次数时，基于已收集信息生成答案"""
        if len(scratchpad) == 0:
            return "抱歉，我无法完成这个任务。请尝试重新描述您的问题。"
        
        # 收集所有 observation
        observations = []
        for entry in scratchpad.entries:
            if entry.observation and not entry.observation.startswith("[ERROR]"):
                observations.append(entry.observation)
        
        if not observations:
            return "抱歉，我在尝试回答您的问题时遇到了困难。请尝试重新描述您的问题。"
        
        # 简单拼接已收集的信息
        collected_info = "\n\n".join(observations[:3])  # 最多取前3个
        return f"基于我收集到的信息：\n\n{collected_info}\n\n（注：由于推理步数限制，答案可能不完整）"
    
    def _chunk_text(self, text: str, chunk_size: int = 50) -> list:
        """将文本分块用于流式输出"""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

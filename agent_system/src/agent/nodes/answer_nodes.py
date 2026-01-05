"""答案生成节点"""
import asyncio
from typing import Dict, Any, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage

from .base import BaseAgentNode
from ..state import AgentState, IntentType
from ..constants import MAX_CONCURRENT_LLM_CALLS
from ...prompts import (
    SINGLE_DOC_SUMMARY_PROMPT,
    MULTI_DOC_SUMMARY_PROMPT,
    REVIEW_GENERATION_PROMPT,
    LITERATURE_QA_PROMPT,
    DOCUMENT_COMPARISON_PROMPT,
    MULTI_DOC_SUMMARY_SYNTHESIS_PROMPT,
    REVIEW_GENERATION_SYNTHESIS_PROMPT,
    MULTI_DOC_SUMMARY_FINAL_MERGE_PROMPT,
    REVIEW_GENERATION_FINAL_MERGE_PROMPT,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)


class AnswerNodes(BaseAgentNode):
    """答案生成节点"""
    
    async def answer_generation_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """答案生成节点"""
        try:
            intent = state['detected_intent']
            doc_count = state.get('doc_count', 0)
            strategy = state.get('strategy')
            
            # 多文档总结模式
            if strategy == "multi_doc_summary":
                async for event in self._handle_multi_doc_summary(state, intent):
                    yield event
                return
            
            # 其他模式
            context_str = await self._get_conversation_context_async(state, stage="answer_generation")
            context_for_llm = self._build_collected_info_for_answer(state)
            
            # 选择提示词
            prompt_template = self._select_prompt_template(intent, doc_count)
            
            prompt = prompt_template.format(
                user_query=state["user_query"],
                conversation_history=context_str if context_str else "无",
                documents_content=context_for_llm if context_for_llm else "无"
            )
            
            full_answer = ""
            async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_answer += chunk_content
                yield {"type": "answer_chunk", "node": "answer_generation", "content": chunk_content}
            
            # 保存会话（使用线程池避免阻塞事件循环）
            session_id = state.get("session_id")
            if session_id:
                model_name = self.llm.model_name if hasattr(self.llm, 'model_name') else "unknown"
                
                if not state.get("_user_message_saved"):
                    await asyncio.to_thread(
                        self.session_manager.add_user_message,
                        session_id=session_id,
                        content=state["user_query"],
                        model_name=model_name
                    )
                
                await asyncio.to_thread(
                    self.session_manager.add_assistant_message,
                    session_id=session_id,
                    content=full_answer,
                    model_name=model_name
                )
            
            result = {
                "final_answer": full_answer,
                "messages": state.get("messages", []) + [AIMessage(content=full_answer)]
            }
            
            yield {"type": "node_complete", "data": result}
        except Exception as e:
            logger.error(f"Error in answer_generation_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "answer_generation", "error": str(e)}
    
    def _select_prompt_template(self, intent: IntentType, doc_count: int) -> str:
        """
        选择提示词模板
        
        Args:
            intent: 意图类型
            doc_count: 文档数量
            
        Returns:
            提示词模板字符串
        """
        if intent == IntentType.LITERATURE_SUMMARY:
            return SINGLE_DOC_SUMMARY_PROMPT if doc_count == 1 else MULTI_DOC_SUMMARY_PROMPT
        elif intent == IntentType.REVIEW_GENERATION:
            return REVIEW_GENERATION_PROMPT
        elif intent == IntentType.LITERATURE_QA:
            return LITERATURE_QA_PROMPT
        elif intent == IntentType.DOCUMENT_COMPARISON:
            return DOCUMENT_COMPARISON_PROMPT
        else:
            # GENERAL_TASK 不应该走到这里，由 ReAct 处理
            return LITERATURE_QA_PROMPT
    
    async def _handle_multi_doc_summary(
        self,
        state: AgentState,
        intent: IntentType
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理多文档总结
        
        处理流程：
        1. 单组场景：直接使用 synthesis 提示词生成最终答案
        2. 多组场景：
           - 先为每组生成中间报告（不流式输出）
           - 再使用 final_merge 提示词合并所有报告（流式输出）
        
        Args:
            state: Agent 状态
            intent: 意图类型
            
        Yields:
            流式事件字典
        """
        document_summaries = state.get("document_summaries", {})
        if not document_summaries:
            yield {"type": "error", "error": "No document summaries found"}
            return
        
        document_names = state.get("document_names", {}) or {}
        
        # 文章对比：不分组，直接使用所有文档总结
        if intent == IntentType.DOCUMENT_COMPARISON:
            summaries_text = "\n\n".join([
                f"## 文档 {i+1}: {document_names.get(doc_id, doc_id)}\n{summary}"
                for i, (doc_id, summary) in enumerate(document_summaries.items())
            ])
            
            prompt = DOCUMENT_COMPARISON_PROMPT.format(
                user_query=state["user_query"],
                documents_summaries=summaries_text
            )
            
            full_answer = ""
            async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_answer += chunk_content
                yield {"type": "answer_chunk", "content": chunk_content}
            
            # 保存会话
            await self._save_session_messages(state, full_answer)
            
            yield {
                "type": "final_answer",
                "data": {
                    "answer": full_answer,
                    "session_id": state.get("session_id", ""),
                    "detected_intent": intent.value if intent else "",
                    "follow_up_questions": state.get("follow_up_questions", [])
                }
            }
            return
        
        max_context_tokens = state.get("max_context_tokens", 100000)
        threshold = int(max_context_tokens * 0.7)
        
        groups = self._smart_split_document_summaries(document_summaries, threshold)
        
        # 选择提示词模板
        if intent == IntentType.LITERATURE_SUMMARY:
            synthesis_prompt_template = MULTI_DOC_SUMMARY_SYNTHESIS_PROMPT
            final_merge_prompt_template = MULTI_DOC_SUMMARY_FINAL_MERGE_PROMPT
        elif intent == IntentType.REVIEW_GENERATION:
            synthesis_prompt_template = REVIEW_GENERATION_SYNTHESIS_PROMPT
            final_merge_prompt_template = REVIEW_GENERATION_FINAL_MERGE_PROMPT
        else:
            yield {"type": "error", "error": f"Unexpected intent: {intent}"}
            return
        
        document_names = state.get("document_names", {}) or {}
        
        if len(groups) == 1:
            # 单组场景：直接生成最终答案
            summaries_text = "\n\n".join([
                f"## 文档 {i+1}: {document_names.get(doc_id, doc_id)}\n{summary}"
                for i, (doc_id, summary) in enumerate(groups[0])
            ])
            
            prompt = synthesis_prompt_template.format(
                user_query=state["user_query"],
                documents_summaries=summaries_text
            )
            
            full_answer = ""
            async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_answer += chunk_content
                yield {"type": "answer_chunk", "content": chunk_content}
            
            # 保存会话
            await self._save_session_messages(state, full_answer)
            
            yield {
                "type": "final_answer",
                "data": {
                    "answer": full_answer,
                    "session_id": state.get("session_id", ""),
                    "detected_intent": intent.value if intent else "",
                    "follow_up_questions": state.get("follow_up_questions", [])
                }
            }
        else:
            # 多组场景：先生成中间报告，再合并
            logger.info(f"📚 多组处理模式：{len(groups)} 组，开始生成中间报告...")
            logger.info(f"⚙️ 并发限制: 最多同时处理 {MAX_CONCURRENT_LLM_CALLS} 组")
            
            # 使用信号量限制并发
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
            
            async def generate_group_report(idx: int, group: list) -> tuple:
                """带信号量限制的分组报告生成"""
                async with semaphore:
                    summaries_text = "\n\n".join([
                        f"## 文档: {document_names.get(doc_id, doc_id)}\n{summary}"
                        for doc_id, summary in group
                    ])
                    prompt = synthesis_prompt_template.format(
                        user_query=state["user_query"],
                        documents_summaries=summaries_text
                    )
                    
                    # 不流式输出中间报告，只收集结果
                    group_answer = ""
                    async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                        chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        group_answer += chunk_content
                    
                    logger.info(f"   ✅ 第 {idx + 1}/{len(groups)} 组报告完成，长度: {len(group_answer)}")
                    return idx, group_answer
            
            # 并行生成所有分组报告（受信号量限制）
            tasks = [generate_group_report(idx, group) for idx, group in enumerate(groups)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 按索引排序结果
            group_reports = [""] * len(groups)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"分组报告生成失败: {result}")
                else:
                    idx, report = result
                    group_reports[idx] = report
            
            logger.info(f"📝 开始合并 {len(group_reports)} 个分组报告...")
            
            # 使用专门的合并提示词
            all_reports_text = "\n\n".join([
                f"# 第 {i+1} 组分析报告\n{report}"
                for i, report in enumerate(group_reports)
            ])
            final_prompt = final_merge_prompt_template.format(
                user_query=state["user_query"],
                group_reports=all_reports_text
            )
            
            # 只流式输出最终合并结果
            full_answer = ""
            async for chunk in self.llm.astream([HumanMessage(content=final_prompt)]):
                chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_answer += chunk_content
                yield {"type": "answer_chunk", "content": chunk_content}
            
            # 保存会话
            await self._save_session_messages(state, full_answer)
            
            yield {
                "type": "final_answer",
                "data": {
                    "answer": full_answer,
                    "session_id": state.get("session_id", ""),
                    "detected_intent": intent.value if intent else "",
                    "follow_up_questions": state.get("follow_up_questions", [])
                }
            }
    
    async def _save_session_messages(self, state: AgentState, answer: str) -> None:
        """
        保存会话消息（用户消息和助手消息）
        
        Args:
            state: Agent 状态
            answer: 助手回答内容
        """
        session_id = state.get("session_id")
        if not session_id:
            return
        
        model_name = self.llm.model_name if hasattr(self.llm, 'model_name') else "unknown"
        
        # 保存用户消息（如果尚未保存）
        if not state.get("_user_message_saved"):
            await asyncio.to_thread(
                self.session_manager.add_user_message,
                session_id=session_id,
                content=state["user_query"],
                model_name=model_name
            )
        
        # 保存助手消息
        await asyncio.to_thread(
            self.session_manager.add_assistant_message,
            session_id=session_id,
            content=answer,
            model_name=model_name
        )

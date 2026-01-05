"""规划相关节点"""
from typing import Dict, Any, List, AsyncGenerator, Optional

from langchain_core.messages import HumanMessage

from .base import BaseAgentNode
from ..state import AgentState, IntentType, Plan, SubQuestion
from ...prompts import (
    INTENT_RECOGNITION_PROMPT,
    SUB_QUESTION_GENERATION_PROMPT,
)
from ...utils.logger import get_logger
from ...utils.json_parser import parse_json_response
from ..constants import MAX_INTENT_RECOGNITION_RETRIES

logger = get_logger(__name__)


class PlanningNodes(BaseAgentNode):
    """意图识别、策略选择和计划生成节点"""
    
    # 意图类型的中文显示名称映射
    INTENT_DISPLAY_NAMES = {
        "LITERATURE_SUMMARY": "文献总结",
        "REVIEW_GENERATION": "综述生成",
        "LITERATURE_QA": "文献问答",
        "DOCUMENT_COMPARISON": "文章对比",
        "GENERAL_TASK": "通用任务"
    }
    
    # Pipeline 路线支持的意图类型
    PIPELINE_INTENTS = {
        IntentType.LITERATURE_SUMMARY,
        IntentType.REVIEW_GENERATION,
        IntentType.LITERATURE_QA,
        IntentType.DOCUMENT_COMPARISON
    }
    
    def _get_intent_display_name(self, intent: str) -> str:
        """将意图类型转换为用户友好的显示名称"""
        return self.INTENT_DISPLAY_NAMES.get(intent, intent)
    
    async def intent_recognition_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """意图识别节点"""
        try:
            mode_type = state.get("mode_type")
            if mode_type:
                try:
                    detected_intent = IntentType(mode_type)
                    route = "pipeline" if detected_intent in self.PIPELINE_INTENTS else "react"
                    # 意图识别结果只记录日志，不输出到前端
                    logger.info(f"使用指定的任务类型: {mode_type} → {route}")
                    
                    document_ids = state.get("document_ids", [])
                    doc_count = len(document_ids) if document_ids else 0
                    yield {"type": "node_complete", "data": {"detected_intent": detected_intent, "doc_count": doc_count, "route": route}}
                    return
                except ValueError:
                    logger.warning("提供的任务类型无效，调用LLM识别")
            
            context_str = await self._get_conversation_context_async(state, stage="intent_recognition")
            
            # 获取文档信息
            document_ids = state.get("document_ids", [])
            doc_count = len(document_ids) if document_ids else 0
            has_documents = "true" if doc_count > 0 else "false"
            
            # 获取北京时间
            from datetime import datetime, timezone, timedelta
            beijing_tz = timezone(timedelta(hours=8))
            current_time = datetime.now(beijing_tz).strftime("%Y年%m月%d日 %H:%M")
            
            prompt = INTENT_RECOGNITION_PROMPT.format(
                current_time=current_time,
                user_query=state["user_query"],
                conversation_history=context_str if context_str else "无",
                has_documents=has_documents,
                document_count=doc_count
            )
            
            # 收集完整响应（不输出中间状态）
            
            full_response = ""
            async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_response += chunk_content
            
            detected_intent = None
            reasoning = ""
            confidence = 0
            
            for attempt in range(MAX_INTENT_RECOGNITION_RETRIES):
                parsed = parse_json_response(full_response, expected_fields=["intent", "reasoning"])
                
                if parsed and "intent" in parsed:
                    try:
                        detected_intent = IntentType(parsed["intent"])
                        reasoning = parsed.get("reasoning", "")
                        confidence = parsed.get("confidence", 0)
                        break
                    except ValueError:
                        pass
                
                intent_str = full_response.strip()
                try:
                    detected_intent = IntentType(intent_str)
                    break
                except ValueError:
                    pass
                
                if attempt < MAX_INTENT_RECOGNITION_RETRIES - 1:
                    full_response = ""
                    async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                        chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        full_response += chunk_content
            
            if detected_intent is None:
                # 默认使用 GENERAL_TASK（由 ReAct 处理）
                detected_intent = IntentType.GENERAL_TASK
            
            # 意图识别结果只记录日志，不输出到前端
            if reasoning:
                logger.info(f"意图识别推理: {reasoning}")
            
            document_ids = state.get("document_ids", [])
            doc_count = len(document_ids) if document_ids else 0
            
            # 确定路由：Pipeline 或 ReAct
            route = "pipeline" if detected_intent in self.PIPELINE_INTENTS else "react"
            
            display_name = self._get_intent_display_name(detected_intent.value)
            route_display = "专用流水线" if route == "pipeline" else "ReAct Agent"
            logger.info(f"识别意图: {display_name} → {route_display}")
            
            yield {"type": "node_complete", "data": {"detected_intent": detected_intent, "doc_count": doc_count, "route": route}}
        except Exception as e:
            logger.error(f"Error in intent_recognition_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "intent_recognition", "error": str(e)}
    
    async def strategy_selection_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """策略选择节点"""
        try:
            if state.get("use_direct_content", False):
                result = {"strategy": "full_content", "use_direct_content": True}
            else:
                document_count = state.get("doc_count", 0)
                detected_intent = state.get("detected_intent")
                
                if document_count > 1:
                    if detected_intent in [IntentType.LITERATURE_SUMMARY, IntentType.REVIEW_GENERATION, IntentType.DOCUMENT_COMPARISON]:
                        result = {"strategy": "multi_doc_summary", "use_direct_content": False}
                    else:
                        result = {"strategy": "chunk_recall", "use_direct_content": False}
                else:
                    result = {"strategy": "chunk_recall", "use_direct_content": False}
            
            # 打印策略选择日志
            logger.info("=" * 60)
            logger.info("🎯 策略选择结果:")
            logger.info(f"   - 文档数量: {state.get('doc_count', 0)}")
            logger.info(f"   - 识别意图: {state.get('detected_intent')}")
            logger.info(f"   - 选择策略: {result.get('strategy')}")
            logger.info("=" * 60)
            
            yield {"type": "node_complete", "data": result}
        except Exception as e:
            logger.error(f"Error in strategy_selection_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "strategy_selection", "error": str(e)}
    
    async def sub_question_generation_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """子问题生成节点"""
        try:
            strategy = state.get("strategy", "chunk_recall")
            if strategy != "chunk_recall":
                yield {"type": "node_complete", "data": {}}
                return
            
            user_query = state["user_query"]
            doc_count = state.get("doc_count", 0)
            document_ids = state.get("document_ids", [])
            document_names = state.get("document_names", {}) or {}
            
            # 构建文档列表：使用文档名称而不是 ID（对 LLM 更有意义）
            if document_ids:
                doc_entries = []
                for doc_id in document_ids:
                    doc_name = document_names.get(doc_id, f"文档_{doc_id[:8]}")
                    doc_entries.append({"id": doc_id, "name": doc_name})
                import json
                doc_list_display = json.dumps(doc_entries, ensure_ascii=False)
            else:
                doc_list_display = "[]"
            
            # 使用 % 格式化避免与 JSON 中的花括号冲突
            prompt = SUB_QUESTION_GENERATION_PROMPT.replace(
                "{user_query}", user_query
            ).replace(
                "{doc_type}", "学术文献"
            ).replace(
                "{need_context}", "否"
            ).replace(
                "{mode}", "Fast"
            ).replace(
                "{document_count}", str(doc_count)
            ).replace(
                "{document_list}", doc_list_display
            )
            
            # 收集完整响应（不输出中间状态）
            
            full_response = ""
            async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_response += chunk_content
            
            sub_questions = parse_json_response(full_response, expected_fields=None)
            
            if not isinstance(sub_questions, list) or len(sub_questions) == 0:
                result = {}
            else:
                result = {"sub_questions": sub_questions}
            
            yield {"type": "node_complete", "data": result}
        except Exception as e:
            logger.error(f"Error in sub_question_generation_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "sub_question_generation", "error": str(e)}
    
    async def plan_generation_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        计划生成节点
        
        将子问题转换为执行计划，如果子问题生成失败则使用原始问题作为单个召回步骤
        """
        try:
            sub_questions = state.get("sub_questions")
            if sub_questions:
                result = self._generate_plan_from_sub_questions(state, sub_questions)
            else:
                # 子问题生成失败时，直接用原始问题作为单个召回步骤
                logger.warning("子问题生成失败，使用原始问题作为召回步骤")
                result = self._generate_fallback_plan(state)
            
            yield {"type": "node_complete", "data": result}
        except Exception as e:
            logger.error(f"Error in plan_generation_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "plan_generation", "error": str(e)}
    
    def _generate_fallback_plan(self, state: AgentState) -> Dict[str, Any]:
        """
        生成 fallback 计划：直接用原始问题作为单个召回步骤
        
        Args:
            state: Agent 状态
            
        Returns:
            包含 plan、current_step_index、execution_results 的字典
        """
        user_query = state["user_query"]
        
        plan = {
            "locale": "zh-CN",
            "thought": "子问题生成失败，使用原始问题进行召回",
            "title": "信息收集",
            "steps": [
                {
                    "title": user_query[:50] + "..." if len(user_query) > 50 else user_query,
                    "step_type": "recall",
                    "target_doc_id": None
                }
            ]
        }
        
        return {"plan": plan, "current_step_index": 0, "execution_results": []}
    
    def _generate_plan_from_sub_questions(
        self,
        state: AgentState,
        sub_questions: List[SubQuestion]
    ) -> Dict[str, Any]:
        """
        从子问题生成执行计划
        
        Args:
            state: Agent 状态
            sub_questions: 子问题列表
            
        Returns:
            包含 plan、current_step_index、execution_results 的字典
        """
        document_ids = state.get("document_ids", [])
        doc_id_map = {doc_id.lower(): doc_id for doc_id in document_ids} if document_ids else {}
        
        steps = []
        for i, sq in enumerate(sub_questions):
            target_doc_id = sq.get("target_doc_id")
            
            if target_doc_id == "" or target_doc_id == "null" or target_doc_id is None:
                target_doc_id = None
            elif document_ids:
                if not isinstance(target_doc_id, str):
                    target_doc_id = None
                elif target_doc_id in document_ids:
                    pass
                elif target_doc_id.lower() in doc_id_map:
                    target_doc_id = doc_id_map[target_doc_id.lower()]
                else:
                    target_doc_id = None
            
            step = {
                "title": sq.get("question", f"子问题 {i+1}"),
                "step_type": "recall",
                "target_doc_id": target_doc_id
            }
            steps.append(step)
        
        plan = {
            "locale": "zh-CN",
            "thought": f"基于子问题生成的执行计划，共 {len(sub_questions)} 个召回步骤",
            "title": "信息收集",
            "steps": steps
        }
        
        return {"plan": plan, "current_step_index": 0, "execution_results": []}

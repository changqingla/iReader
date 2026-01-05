"""执行相关节点"""
import asyncio
from typing import Dict, Any, List, AsyncGenerator, Optional

from .base import BaseAgentNode, RecallStepInfo, StepWithQuery
from ..state import AgentState, StepType, ExecutionResult
from ...utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionNodes(BaseAgentNode):
    """执行节点"""
    
    async def execution_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """执行节点"""
        try:
            plan = state.get("plan")
            if not plan:
                yield {"type": "node_complete", "data": {}}
                return
            
            steps = plan.get("steps", [])
            current_step_index = state.get("current_step_index", 0)
            
            if current_step_index >= len(steps):
                yield {"type": "node_complete", "data": {"current_step_index": current_step_index}}
                return
            
            # 检查是否需要并行执行
            if current_step_index == 0:
                consecutive_recall_steps = []
                for i, step in enumerate(steps):
                    if step["step_type"] == "recall":
                        consecutive_recall_steps.append({"index": i, "step": step})
                    else:
                        break
                
                if len(consecutive_recall_steps) > 1:
                    
                    steps_with_queries = self._generate_queries(consecutive_recall_steps, state)
                    execution_results = await self._execute_recall_async(steps_with_queries)
                    
                    result = {
                        "execution_results": state.get("execution_results", []) + execution_results,
                        "current_step_index": len(consecutive_recall_steps)
                    }
                else:
                    current_step = steps[current_step_index]
                    step_with_query = self._generate_queries([{"index": current_step_index, "step": current_step}], state)[0]
                    execution_results = await self._execute_recall_async([step_with_query])
                    
                    result = {
                        "execution_results": state.get("execution_results", []) + execution_results,
                        "current_step_index": current_step_index + 1
                    }
            else:
                current_step = steps[current_step_index]
                step_with_query = self._generate_queries([{"index": current_step_index, "step": current_step}], state)[0]
                execution_results = await self._execute_recall_async([step_with_query])
                
                result = {
                    "execution_results": state.get("execution_results", []) + execution_results,
                    "current_step_index": current_step_index + 1
                }
            
            # 不输出召回完成信息
            
            yield {"type": "node_complete", "data": result}
        except Exception as e:
            logger.error(f"Error in execution_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "execution", "error": str(e)}
    
    def _generate_queries(
        self,
        recall_steps: List[RecallStepInfo],
        state: AgentState
    ) -> List[StepWithQuery]:
        """
        生成查询
        
        Args:
            recall_steps: 召回步骤列表
            state: Agent 状态
            
        Returns:
            带查询的步骤列表
        """
        sub_questions = state.get("sub_questions")
        if sub_questions:
            return self._use_sub_questions_as_queries(recall_steps, sub_questions)
        
        steps_with_queries = []
        for step_info in recall_steps:
            step_index = step_info["index"]
            step = step_info["step"]
            query = step["title"]
            
            steps_with_queries.append({
                "index": step_index,
                "step": step,
                "query": query,
                "decision": {"need_tool": True, "tool_name": "recall", "query": query, "reasoning": "使用步骤标题作为查询"}
            })
        
        return steps_with_queries
    
    def _use_sub_questions_as_queries(
        self,
        recall_steps: List[RecallStepInfo],
        sub_questions: List[Dict[str, Any]]
    ) -> List[StepWithQuery]:
        """
        使用子问题作为查询
        
        Args:
            recall_steps: 召回步骤列表
            sub_questions: 子问题列表
            
        Returns:
            带查询的步骤列表
        """
        steps_with_queries = []
        
        for step_info in recall_steps:
            step_index = step_info["index"]
            step = step_info["step"]
            step_title = step["title"]
            
            query = step_title
            for sq in sub_questions:
                if sq.get("question") == step_title:
                    query = sq.get("question")
                    break
            
            steps_with_queries.append({
                "index": step_index,
                "step": step,
                "query": query,
                "decision": {"need_tool": True, "tool_name": "recall", "query": query, "reasoning": "子问题模式"}
            })
        
        return steps_with_queries
    
    async def _execute_recall_async(
        self,
        steps_with_queries: List[StepWithQuery]
    ) -> List[ExecutionResult]:
        """
        异步并行执行召回
        
        Args:
            steps_with_queries: 带查询的步骤列表
            
        Returns:
            执行结果列表
        """
        async def execute_single_recall(step_with_query: Dict) -> ExecutionResult:
            step_index = step_with_query["index"]
            step = step_with_query["step"]
            query = step_with_query["query"]
            
            try:
                result_with_source = await self._perform_recall_async(query, step)
                
                return {
                    "step_index": step_index,
                    "step_title": step["title"],
                    "step_type": StepType.RECALL,
                    "tool_used": "recall",
                    "query": query,
                    "result": result_with_source,
                    "error": None,
                    "target_doc_id": step.get("target_doc_id")
                }
            except Exception as e:
                logger.error(f"Step {step_index + 1}: 召回错误: {str(e)}", exc_info=True)
                return {
                    "step_index": step_index,
                    "step_title": step["title"],
                    "step_type": StepType.RECALL,
                    "tool_used": "recall",
                    "query": query,
                    "result": f"召回失败: {str(e)}",
                    "error": str(e),
                    "target_doc_id": step.get("target_doc_id")
                }
        
        # 使用 asyncio.gather 并行执行所有召回任务
        tasks = [execute_single_recall(sq) for sq in steps_with_queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        execution_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                step_with_query = steps_with_queries[i]
                execution_results.append({
                    "step_index": step_with_query["index"],
                    "step_title": step_with_query["step"]["title"],
                    "step_type": StepType.RECALL,
                    "tool_used": "recall",
                    "query": step_with_query["query"],
                    "result": f"召回失败: {str(result)}",
                    "error": str(result),
                    "target_doc_id": step_with_query["step"].get("target_doc_id")
                })
            else:
                execution_results.append(result)
        
        execution_results.sort(key=lambda x: x["step_index"])
        return execution_results
    
    async def _perform_recall_async(
        self,
        query: str,
        step: Dict[str, Any]
    ) -> str:
        """
        异步执行召回操作
        
        Args:
            query: 查询字符串
            step: 步骤信息
            
        Returns:
            召回结果文本
        """
        target_doc_id = step.get("target_doc_id")
        
        if target_doc_id:
            logger.info(f"📄 分文档召回：{target_doc_id}")
            single_doc_tool = self._recall_cache.get_or_create(
                doc_id=target_doc_id,
                base_tool=self.recall_tool
            )
            tool_result = await single_doc_tool._arun(query)
            return f"【文档: {target_doc_id}】\n{tool_result}"
        else:
            logger.info("📚 混合召回模式")
            tool_result = await self.recall_tool._arun(query)
            return tool_result

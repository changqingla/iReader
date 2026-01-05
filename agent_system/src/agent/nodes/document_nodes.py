"""文档相关节点"""
import asyncio
from typing import Dict, Any, AsyncGenerator, Callable, Awaitable

from langchain_core.messages import HumanMessage

from .base import BaseAgentNode
from ..state import AgentState, IntentType
from ..constants import MAX_CONCURRENT_LLM_CALLS
from ...prompts import DOCUMENT_CONDENSED_SUMMARY_PROMPT
from ...utils.logger import get_logger
from ...utils.document_summary_cache import get_document_summary_cache
from context.token_counter import calculate_tokens
from config import get_settings

logger = get_logger(__name__)

# 单篇文档总结的最大 token 阈值（使用 direct_content_threshold 配置）
# 超过此阈值的文档将使用召回模式生成总结


class DocumentNodes(BaseAgentNode):
    """文档检查和总结节点"""
    
    @property
    def large_doc_summary_top_n(self) -> int:
        """大文档总结时的召回数量（从配置文件加载）"""
        return get_settings().large_doc_summary_top_n
    
    async def document_check_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """文档检查节点"""
        try:
            document_ids = state.get("document_ids", [])
            doc_count = len(document_ids) if document_ids else 0
            direct_content = state.get("direct_content")
            
            if doc_count == 0 and not direct_content:
                result = {
                    "detected_intent": IntentType.GENERAL_TASK,  # 无文档时走 ReAct
                    "doc_count": doc_count,
                    "route": "react",  # 直接设置路由
                    "messages": state.get("messages", []) + [
                        HumanMessage(content=state["user_query"])
                    ]
                }
            else:
                result = {"doc_count": doc_count}
            
            yield {"type": "node_complete", "data": result}
        except Exception as e:
            logger.error(f"Error in document_check_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "document_check", "error": str(e)}

    async def document_summary_node_stream(
        self,
        state: AgentState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        多文档总结节点（有限并发 + 流式输出）
        
        为每个文档生成压缩总结，用于后续的综合分析。
        支持实时流式输出每个文档的处理进度。
        
        缓存机制：
        - 默认使用缓存，避免重复生成相同文档的总结
        - 可通过 refresh_summary_cache=True 强制刷新缓存
        
        对于每篇文档：
        - 如果内容小于阈值：直接使用完整内容生成总结
        - 如果内容超过阈值：使用召回获取关键信息后生成总结
        
        Args:
            state: Agent 状态
            
        Yields:
            流式事件字典，包括：
            - doc_summary_start: 文档开始处理
            - doc_summary_chunk: 文档总结内容片段
            - doc_summary_complete: 文档处理完成
            - thought_chunk: 思考过程文本
            - node_complete: 节点完成
        """
        try:
            document_contents = state.get("document_contents", {})
            document_ids = state.get("document_ids", [])
            document_names = state.get("document_names", {})  # 文档名称映射
            max_context_tokens = state.get("max_context_tokens", 100000)
            refresh_cache = state.get("refresh_summary_cache", False)
            
            if not document_contents and not document_ids:
                yield {"type": "node_error", "node": "document_summary", "error": "无文档内容"}
                return
            
            # 过滤有效文档
            valid_docs = {doc_id: document_contents.get(doc_id, "")
                         for doc_id in document_ids 
                         if document_contents.get(doc_id)}
            
            if not valid_docs:
                yield {"type": "node_error", "node": "document_summary", "error": "无有效文档内容"}
                return
            
            # 获取缓存实例
            summary_cache = get_document_summary_cache()
            
            # 批量查询缓存
            cached_summaries, uncached_docs = summary_cache.get_batch(
                valid_docs, 
                skip_cache=refresh_cache
            )
            
            cache_hit_count = len(cached_summaries)
            cache_miss_count = len(uncached_docs)
            total_docs = len(valid_docs)
            
            # 发送文档总结初始化事件
            yield {
                "type": "doc_summary_init",
                "data": {
                    "total": total_docs,
                    "cached": cache_hit_count,
                    "to_generate": cache_miss_count
                }
            }
            
            # 不输出处理状态，文档进度通过 doc_summary_* 事件展示
            
            # 详细的缓存日志
            logger.info("=" * 60)
            logger.info(f"📦 文档总结缓存状态:")
            logger.info(f"   - 总文档数: {total_docs}")
            logger.info(f"   - 缓存命中: {cache_hit_count}")
            logger.info(f"   - 缓存未命中: {cache_miss_count}")
            logger.info(f"   - 强制刷新: {refresh_cache}")
            if cached_summaries:
                logger.info(f"   - 命中的文档ID: {list(cached_summaries.keys())[:5]}{'...' if len(cached_summaries) > 5 else ''}")
            if uncached_docs:
                logger.info(f"   - 未命中的文档ID: {list(uncached_docs.keys())[:5]}{'...' if len(uncached_docs) > 5 else ''}")
            logger.info("=" * 60)
            
            # 为缓存命中的文档发送完成事件
            cached_index = 0
            for doc_id, summary in cached_summaries.items():
                doc_name = document_names.get(doc_id, f"文档 {cached_index + 1}")
                yield {
                    "type": "doc_summary_complete",
                    "data": {
                        "doc_id": doc_id,
                        "doc_name": doc_name,
                        "summary": summary,
                        "from_cache": True,
                        "index": cached_index,
                        "total": total_docs
                    }
                }
                cached_index += 1
            
            # 如果所有文档都命中缓存，直接返回
            if cache_miss_count == 0 and not refresh_cache:
                logger.info(f"✅ 所有 {cache_hit_count} 篇文档总结已从缓存加载，跳过 LLM 调用")
                yield {
                    "type": "node_complete",
                    "data": {"document_summaries": cached_summaries}
                }
                return
            
            # 计算单篇文档的 token 阈值
            settings = get_settings()
            single_doc_threshold = int(max_context_tokens * settings.direct_content_threshold)
            
            # 分类需要生成的文档：小文档直接处理，大文档需要召回
            small_docs = []
            large_docs = []
            
            docs_to_process = uncached_docs if not refresh_cache else valid_docs
            
            for doc_id, content in docs_to_process.items():
                token_count = calculate_tokens(content)
                if token_count <= single_doc_threshold:
                    small_docs.append((doc_id, content, token_count))
                    logger.info(f"文档 {doc_id}: {token_count:,} tokens (直接处理)")
                else:
                    large_docs.append((doc_id, content, token_count))
                    logger.info(f"文档 {doc_id}: {token_count:,} tokens (需要召回，阈值: {single_doc_threshold:,})")
            
            # 不输出文档分类信息
            
            # 使用信号量限制并发 LLM 调用数
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
            docs_to_generate = len(small_docs) + len(large_docs)
            
            logger.info(f"📊 开始并行处理 {docs_to_generate} 篇文档，最大并发数: {MAX_CONCURRENT_LLM_CALLS}")
            
            # 创建事件队列用于流式输出
            event_queue: asyncio.Queue = asyncio.Queue()
            
            async def summarize_with_progress(doc_id: str, content: str, is_large: bool, index: int):
                """带进度输出的文档总结（大文档和小文档都支持流式输出）"""
                doc_name = document_names.get(doc_id, f"文档 {index + 1}")
                
                async with semaphore:
                    # 发送开始事件
                    await event_queue.put({
                        "type": "doc_summary_start",
                        "data": {
                            "doc_id": doc_id,
                            "doc_name": doc_name,
                            "index": index,
                            "total": total_docs
                        }
                    })
                    
                    try:
                        # 定义流式输出回调
                        async def on_chunk(chunk_content: str):
                            await event_queue.put({
                                "type": "doc_summary_chunk",
                                "data": {
                                    "doc_id": doc_id,
                                    "content": chunk_content
                                }
                            })
                        
                        if is_large:
                            # 大文档使用召回模式（现在也支持流式输出）
                            summary = await self._summarize_large_document_with_recall_stream(
                                doc_id, state, on_chunk
                            )
                        else:
                            # 小文档流式生成总结
                            summary = ""
                            prompt = DOCUMENT_CONDENSED_SUMMARY_PROMPT.format(document_content=content)
                            
                            chunk_count = 0
                            logger.info(f"📝 文档 {doc_id} 开始流式生成总结...")
                            try:
                                async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                                    #logger.info(f"📝 文档 {doc_id} 收到原始 chunk: type={type(chunk)}, chunk={str(chunk)[:100]}")
                                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                                    summary += chunk_content
                                    chunk_count += 1
                                    #if chunk_count <= 5:
                                        #logger.info(f"📝 文档 {doc_id} 收到 chunk #{chunk_count}, 长度: {len(chunk_content)}, 内容: {chunk_content[:50]}")
                                    # 发送流式内容
                                    await on_chunk(chunk_content)
                                logger.info(f"✅ 文档 {doc_id} 流式生成完成，共 {chunk_count} 个 chunk，总长度: {len(summary)}")
                            except Exception as e:
                                logger.error(f"❌ 文档 {doc_id} 流式生成异常: {e}", exc_info=True)
                                raise
                        
                        # 发送完成事件
                        await event_queue.put({
                            "type": "doc_summary_complete",
                            "data": {
                                "doc_id": doc_id,
                                "doc_name": doc_name,
                                "summary": summary,
                                "from_cache": False,
                                "index": index,
                                "total": total_docs
                            }
                        })
                        
                        return doc_id, summary, content
                        
                    except Exception as e:
                        logger.error(f"文档 {doc_id} 总结失败: {e}")
                        await event_queue.put({
                            "type": "doc_summary_error",
                            "data": {
                                "doc_id": doc_id,
                                "doc_name": doc_name,
                                "error": str(e)
                            }
                        })
                        return doc_id, f"[文档总结失败: {str(e)}]", content
            
            # 创建所有任务
            tasks = []
            current_index = cache_hit_count  # 从缓存命中数开始计数
            
            # 小文档任务
            for doc_id, content, _ in small_docs:
                tasks.append(summarize_with_progress(doc_id, content, is_large=False, index=current_index))
                current_index += 1
            
            # 大文档任务
            for doc_id, content, _ in large_docs:
                tasks.append(summarize_with_progress(doc_id, content, is_large=True, index=current_index))
                current_index += 1
            
            # 并行执行任务，同时消费事件队列
            async def run_tasks():
                results = await asyncio.gather(*tasks, return_exceptions=True)
                await event_queue.put(None)  # 发送结束信号
                return results
            
            # 启动任务
            task_runner = asyncio.create_task(run_tasks())
            
            # 消费事件队列并 yield
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                # 🔍 Debug: Log event being yielded
                # if event.get("type") == "doc_summary_chunk":
                #     logger.info(f"📤 [Queue] Yielding doc_summary_chunk: doc_id={event.get('data', {}).get('doc_id')}, content_len={len(event.get('data', {}).get('content', ''))}")
                # 
                yield event
            
            # 等待所有任务完成并获取结果
            results = await task_runner
            
            # 处理结果并存入缓存
            new_summaries = {}
            docs_for_cache = {}
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"文档总结失败: {result}")
                else:
                    doc_id, summary, content = result
                    new_summaries[doc_id] = summary
                    docs_for_cache[doc_id] = content
                    logger.info(f"文档 {doc_id} 总结完成，长度: {len(summary)}")
            
            # 批量存入缓存
            if new_summaries:
                saved_count = summary_cache.set_batch(docs_for_cache, new_summaries)
                logger.info(f"💾 已将 {saved_count} 篇新生成的文档总结存入缓存")
            
            # 合并缓存命中和新生成的总结
            document_summaries = {**cached_summaries, **new_summaries}
            
            yield {
                "type": "node_complete",
                "data": {"document_summaries": document_summaries}
            }
            
        except Exception as e:
            logger.error(f"Error in document_summary_node_stream: {str(e)}", exc_info=True)
            yield {"type": "node_error", "node": "document_summary", "error": str(e)}
    
    async def _summarize_large_document_with_recall_stream(
        self,
        doc_id: str,
        state: AgentState,
        on_chunk: Callable[[str], Awaitable[None]]
    ) -> str:
        """
        使用召回模式生成大文档的总结（流式输出版本）
        
        对于超过阈值的大文档，先通过召回获取关键信息，再流式生成总结。
        使用更大的 top_n (35) 以覆盖文档的更多内容。
        
        Args:
            doc_id: 文档ID
            state: Agent 状态（用于获取召回工具配置）
            on_chunk: 流式输出回调函数
            
        Returns:
            文档总结文本
        """
        from ...tools import create_recall_tool
        
        # 为大文档总结创建专用的召回工具，使用更大的 top_n
        large_doc_recall_tool = create_recall_tool(
            api_url=self.recall_tool.api_url,
            index_names=self.recall_tool.index_names,
            es_host=self.recall_tool.es_host,
            model_base_url=self.recall_tool.model_base_url,
            api_key=self.recall_tool.api_key,
            doc_ids=[doc_id],
            top_n=self.large_doc_summary_top_n,  # 从配置文件加载
            similarity_threshold=self.recall_tool.similarity_threshold,
            vector_similarity_weight=self.recall_tool.vector_similarity_weight,
            model_factory=self.recall_tool.model_factory,
            model_name=self.recall_tool.model_name,
            use_rerank=self.recall_tool.use_rerank,
            rerank_factory=self.recall_tool.rerank_factory,
            rerank_model_name=self.recall_tool.rerank_model_name,
            rerank_base_url=self.recall_tool.rerank_base_url,
            rerank_api_key=self.recall_tool.rerank_api_key
        )
        
        # 使用通用查询获取文档的关键信息
        try:
            logger.info(f"📚 大文档 {doc_id} 开始召回，top_n={self.large_doc_summary_top_n}")
            recalled_content = await large_doc_recall_tool._arun(
                "总结这篇文献的主要内容"
            )
        except Exception as e:
            logger.error(f"文档 {doc_id} 召回失败: {e}")
            return f"[文档 {doc_id} 总结生成失败：无法获取文档内容]"
        
        if not recalled_content or not recalled_content.strip():
            logger.warning(f"文档 {doc_id} 召回结果为空")
            return f"[文档 {doc_id} 总结生成失败：召回结果为空]"
        
        logger.info(f"文档 {doc_id} 召回内容长度: {len(recalled_content)} 字符")
        
        # 使用召回内容流式生成总结
        prompt = DOCUMENT_CONDENSED_SUMMARY_PROMPT.format(document_content=recalled_content)
        
        summary = ""
        chunk_count = 0
        logger.info(f"📝 大文档 {doc_id} 开始流式生成总结...")
        async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
            chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            summary += chunk_content
            chunk_count += 1
            # if chunk_count <= 3 or chunk_count % 50 == 0:
            #     logger.info(f"📝 大文档 {doc_id} 收到 chunk #{chunk_count}, 长度: {len(chunk_content)}")
            # 发送流式内容
            await on_chunk(chunk_content)
        
        #logger.info(f"✅ 大文档 {doc_id} 流式生成完成，共 {chunk_count} 个 chunk，总长度: {len(summary)}")
        return summary

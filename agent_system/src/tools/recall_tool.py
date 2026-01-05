"""文档召回工具 - 使用远程 HTTP API"""
import asyncio
import httpx
from typing import Dict, Any, List, Optional

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from ..utils.logger import get_logger

logger = get_logger(__name__)

# HTTP 超时配置
HTTP_TIMEOUT = 120.0


class RecallTool(BaseTool):
    """文档召回工具 - 通过 HTTP API 检索文档知识库"""
    
    name: str = "recall"
    description: str = """从文档知识库中检索相关信息。

使用场景：
- 查找内部文档
- 检索历史记录
- 获取规范、标准文档
- 查询产品信息、技术文档等

输入：检索查询文本（query）
输出：相关文档片段
"""
    
    # API 配置
    api_url: str
    index_names: List[str]
    doc_ids: Optional[List[str]] = None
    es_host: str
    top_n: int = 10
    similarity_threshold: float = 0.2
    vector_similarity_weight: float = 0.3
    
    # 模型配置
    model_factory: str = "VLLM"
    model_name: str = "bge-m3"
    model_base_url: str
    api_key: str
    
    # 重排序配置
    use_rerank: bool = False
    rerank_factory: Optional[str] = None
    rerank_model_name: Optional[str] = None
    rerank_base_url: Optional[str] = None
    rerank_api_key: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def _build_payload(self, query: str) -> Dict[str, Any]:
        """构建 API 请求参数"""
        payload = {
            "question": query,
            "index_names": self.index_names,
            "es_host": self.es_host,
            "top_n": self.top_n,
            "similarity_threshold": self.similarity_threshold,
            "vector_similarity_weight": self.vector_similarity_weight,
            "model_factory": self.model_factory,
            "model_name": self.model_name,
            "model_base_url": self.model_base_url,
            "api_key": self.api_key
        }
        
        if self.doc_ids:
            payload["doc_ids"] = self.doc_ids
        
        if self.use_rerank and self.rerank_model_name:
            payload.update({
                "rerank_factory": self.rerank_factory,
                "rerank_model_name": self.rerank_model_name,
                "rerank_base_url": self.rerank_base_url,
                "rerank_api_key": self.rerank_api_key
            })
        
        return payload
    
    def _format_response(self, result: Dict[str, Any]) -> str:
        """格式化 API 响应"""
        if not result.get("success"):
            error_msg = result.get("message", "Unknown error")
            logger.error(f"Recall API 返回错误: {error_msg}")
            return f"检索失败: {error_msg}"
        
        data = result.get("data", {})
        chunks = data.get("chunks", [])
        
        logger.info(f"Recall API 响应 - total: {data.get('total')}, chunks: {len(chunks)}")
        
        if not chunks:
            logger.warning(f"未返回结果，可能被相似度阈值过滤: {self.similarity_threshold}")
            return "未找到相关信息。"
        
        formatted_results = []
        for i, chunk in enumerate(chunks, 1):
            doc_name = chunk.get("docnm_kwd", "Unknown")
            content = chunk.get("content_with_weight", "")
            page_nums = chunk.get("page_num_int", [])
            
            result_str = f"【文档 {i}】\n来源：{doc_name}"
            if page_nums:
                result_str += f" (第{page_nums[0]}页)"
            result_str += f"\n内容：{content}\n"
            formatted_results.append(result_str)
        
        logger.info(f"召回完成，返回 {len(formatted_results)} 个结果")
        return "\n".join(formatted_results)
    
    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """同步执行文档召回（LangChain BaseTool 要求）"""
        try:
            logger.info(f"执行召回: {query[:100]}...")
            payload = self._build_payload(query)
            
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                response = client.post(self.api_url, json=payload)
                response.raise_for_status()
                result = response.json()
            
            return self._format_response(result)
            
        except httpx.TimeoutException:
            logger.error("Recall API 请求超时")
            raise RuntimeError("Recall API 请求超时")
        except httpx.HTTPError as e:
            logger.error(f"Recall API 请求失败: {str(e)}")
            raise RuntimeError(f"Recall API 请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"召回出错: {str(e)}")
            raise RuntimeError(f"召回出错: {str(e)}")
    
    async def _arun(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """异步执行文档召回"""
        try:
            logger.info(f"异步召回: {query[:100]}...")
            payload = self._build_payload(query)
            
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                result = response.json()
            
            return self._format_response(result)
            
        except httpx.TimeoutException:
            logger.error("Recall API 请求超时")
            raise RuntimeError("Recall API 请求超时")
        except httpx.HTTPError as e:
            logger.error(f"Recall API 请求失败: {str(e)}")
            raise RuntimeError(f"Recall API 请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"异步召回出错: {str(e)}")
            raise RuntimeError(f"异步召回出错: {str(e)}")
    
    async def get_document_name_async(self, doc_id: str) -> Optional[str]:
        """异步获取文档名称"""
        try:
            payload = {
                "question": "获取文档信息",
                "index_names": self.index_names,
                "es_host": self.es_host,
                "top_n": 1,
                "similarity_threshold": 0.0,
                "vector_similarity_weight": self.vector_similarity_weight,
                "model_factory": self.model_factory,
                "model_name": self.model_name,
                "model_base_url": self.model_base_url,
                "api_key": self.api_key,
                "doc_ids": [doc_id]
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                result = response.json()
            
            if result.get("success"):
                chunks = result.get("data", {}).get("chunks", [])
                if chunks:
                    return chunks[0].get("docnm_kwd")
            
            return None
            
        except Exception as e:
            logger.error(f"获取文档名称异常: {doc_id}, error: {str(e)}")
            return None
    
    async def get_document_names_batch_async(self, doc_ids: List[str]) -> Dict[str, str]:
        """异步批量获取文档名称"""
        async def fetch_name(doc_id: str) -> tuple:
            name = await self.get_document_name_async(doc_id)
            return doc_id, name
        
        tasks = [fetch_name(doc_id) for doc_id in doc_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        document_names = {}
        for result in results:
            if isinstance(result, tuple):
                doc_id, name = result
                if name:
                    document_names[doc_id] = name
        
        logger.info(f"批量获取文档名称完成: {len(document_names)}/{len(doc_ids)}")
        return document_names


def create_recall_tool(
    api_url: str,
    index_names: List[str],
    es_host: str,
    model_base_url: str,
    api_key: str,
    doc_ids: Optional[List[str]] = None,
    top_n: int = 10,
    similarity_threshold: float = 0.2,
    vector_similarity_weight: float = 0.3,
    model_factory: str = "VLLM",
    model_name: str = "bge-m3",
    use_rerank: bool = False,
    rerank_factory: Optional[str] = None,
    rerank_model_name: Optional[str] = None,
    rerank_base_url: Optional[str] = None,
    rerank_api_key: Optional[str] = None
) -> RecallTool:
    """创建配置好的 RecallTool 实例"""
    return RecallTool(
        api_url=api_url,
        index_names=index_names,
        doc_ids=doc_ids,
        es_host=es_host,
        top_n=top_n,
        similarity_threshold=similarity_threshold,
        vector_similarity_weight=vector_similarity_weight,
        model_factory=model_factory,
        model_name=model_name,
        model_base_url=model_base_url,
        api_key=api_key,
        use_rerank=use_rerank,
        rerank_factory=rerank_factory,
        rerank_model_name=rerank_model_name,
        rerank_base_url=rerank_base_url,
        rerank_api_key=rerank_api_key
    )

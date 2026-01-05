"""RecallTool 缓存管理"""
from typing import Dict, List, Optional
from collections import OrderedDict

from ..tools import RecallTool, create_recall_tool
from .logger import get_logger
from config import get_settings

logger = get_logger(__name__)


class RecallToolCache:
    """
    RecallTool 实例缓存，避免重复创建
    
    使用 LRU 策略管理缓存，超过阈值时驱逐最久未使用的条目
    """
    
    def __init__(self, max_size: Optional[int] = None):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数。如果为 None，从配置文件加载。
        """
        self._cache: OrderedDict[str, RecallTool] = OrderedDict()
        self._max_size = max_size or get_settings().recall_tool_cache_size
    
    def get_or_create(
        self,
        doc_id: str,
        base_tool: RecallTool
    ) -> RecallTool:
        """
        获取或创建单文档 RecallTool
        
        Args:
            doc_id: 文档 ID
            base_tool: 基础 RecallTool（用于复制配置）
            
        Returns:
            缓存的或新创建的 RecallTool 实例
        """
        if doc_id in self._cache:
            # 移动到末尾（最近使用）
            self._cache.move_to_end(doc_id)
            logger.debug(f"RecallTool cache hit: {doc_id}")
            return self._cache[doc_id]
        
        # 检查缓存大小
        if len(self._cache) >= self._max_size:
            # 驱逐最久未使用的条目（第一个）
            oldest_key, _ = self._cache.popitem(last=False)
            logger.debug(f"RecallTool cache evicted: {oldest_key}")
        
        # 创建新实例
        tool = create_recall_tool(
            api_url=base_tool.api_url,
            index_names=base_tool.index_names,
            es_host=base_tool.es_host,
            model_base_url=base_tool.model_base_url,
            api_key=base_tool.api_key,
            doc_ids=[doc_id],
            top_n=base_tool.top_n,
            similarity_threshold=base_tool.similarity_threshold,
            vector_similarity_weight=base_tool.vector_similarity_weight,
            model_factory=base_tool.model_factory,
            model_name=base_tool.model_name,
            use_rerank=base_tool.use_rerank,
            rerank_factory=base_tool.rerank_factory,
            rerank_model_name=base_tool.rerank_model_name,
            rerank_base_url=base_tool.rerank_base_url,
            rerank_api_key=base_tool.rerank_api_key
        )
        
        self._cache[doc_id] = tool
        logger.debug(f"RecallTool cache miss, created: {doc_id}")
        return tool
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.debug("RecallTool cache cleared")
    
    def size(self) -> int:
        """返回当前缓存大小"""
        return len(self._cache)

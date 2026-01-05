"""
文档总结缓存

全局共享的文档压缩总结缓存，用于避免重复生成相同文档的总结。
缓存键基于 doc_id 和内容哈希，与用户无关，支持跨用户复用。
"""

import hashlib
import json
import redis
from typing import Optional, Dict, Tuple
from config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 缓存键前缀
CACHE_KEY_PREFIX = "doc_summary"
# 默认缓存过期时间（365天）
DEFAULT_CACHE_TTL = 365 * 24 * 60 * 60


class DocumentSummaryCache:
    """
    文档总结缓存
    
    使用 Redis 存储文档的压缩总结，支持：
    - 全局共享：同一文档的总结可被所有用户复用
    - 内容感知：基于内容哈希，文档内容变化时自动失效
    - 强制刷新：支持跳过缓存强制重新生成
    """
    
    def __init__(self):
        """初始化缓存连接"""
        settings = get_settings()
        
        # Redis 连接配置
        redis_kwargs = {
            'host': settings.redis_host,
            'port': settings.redis_port,
            'db': settings.redis_db,
            'socket_timeout': settings.redis_socket_timeout,
            'socket_connect_timeout': settings.redis_socket_connect_timeout,
            'decode_responses': True
        }
        
        if settings.redis_password:
            redis_kwargs['password'] = settings.redis_password
            if settings.redis_username:
                redis_kwargs['username'] = settings.redis_username
        
        self.redis_client = redis.Redis(**redis_kwargs)
        self.enabled = settings.enable_cache
        
        logger.info("DocumentSummaryCache initialized")
    
    @staticmethod
    def compute_content_hash(content: str) -> str:
        """
        计算内容哈希值
        
        Args:
            content: 文档内容
            
        Returns:
            内容的 MD5 哈希值（前 16 位）
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
    
    def _build_cache_key(self, doc_id: str, content_hash: str) -> str:
        """
        构建缓存键
        
        格式: doc_summary:{doc_id}:{content_hash}
        
        Args:
            doc_id: 文档ID
            content_hash: 内容哈希
            
        Returns:
            缓存键字符串
        """
        return f"{CACHE_KEY_PREFIX}:{doc_id}:{content_hash}"
    
    def get(self, doc_id: str, content: str) -> Optional[str]:
        """
        获取缓存的文档总结
        
        Args:
            doc_id: 文档ID
            content: 文档内容（用于计算哈希）
            
        Returns:
            缓存的总结文本，未命中返回 None
        """
        if not self.enabled:
            return None
        
        try:
            content_hash = self.compute_content_hash(content)
            cache_key = self._build_cache_key(doc_id, content_hash)
            
            cached = self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"文档总结缓存命中: {doc_id}")
                return cached
            
            return None
        except Exception as e:
            logger.warning(f"读取文档总结缓存失败: {e}")
            return None
    
    def set(self, doc_id: str, content: str, summary: str, ttl: int = DEFAULT_CACHE_TTL) -> bool:
        """
        存储文档总结到缓存
        
        Args:
            doc_id: 文档ID
            content: 文档内容（用于计算哈希）
            summary: 生成的总结
            ttl: 缓存过期时间（秒），默认 7 天
            
        Returns:
            是否存储成功
        """
        if not self.enabled:
            return False
        
        try:
            content_hash = self.compute_content_hash(content)
            cache_key = self._build_cache_key(doc_id, content_hash)
            
            self.redis_client.setex(cache_key, ttl, summary)
            logger.debug(f"文档总结已缓存: {doc_id}, TTL={ttl}s")
            return True
        except Exception as e:
            logger.warning(f"存储文档总结缓存失败: {e}")
            return False
    
    def delete(self, doc_id: str, content: str) -> bool:
        """
        删除指定文档的缓存
        
        Args:
            doc_id: 文档ID
            content: 文档内容（用于计算哈希）
            
        Returns:
            是否删除成功
        """
        if not self.enabled:
            return False
        
        try:
            content_hash = self.compute_content_hash(content)
            cache_key = self._build_cache_key(doc_id, content_hash)
            
            self.redis_client.delete(cache_key)
            logger.debug(f"文档总结缓存已删除: {doc_id}")
            return True
        except Exception as e:
            logger.warning(f"删除文档总结缓存失败: {e}")
            return False
    
    def get_batch(
        self,
        docs: Dict[str, str],
        skip_cache: bool = False
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        批量获取文档总结缓存
        
        Args:
            docs: 文档字典 {doc_id: content}
            skip_cache: 是否跳过缓存（强制刷新模式）
            
        Returns:
            (cached_summaries, uncached_docs) 元组
            - cached_summaries: 命中缓存的总结 {doc_id: summary}
            - uncached_docs: 未命中的文档 {doc_id: content}
        """
        if not self.enabled or skip_cache:
            return {}, docs
        
        cached_summaries = {}
        uncached_docs = {}
        
        try:
            # 构建所有缓存键
            keys_map = {}  # cache_key -> doc_id
            for doc_id, content in docs.items():
                content_hash = self.compute_content_hash(content)
                cache_key = self._build_cache_key(doc_id, content_hash)
                keys_map[cache_key] = doc_id
            
            # 批量获取
            if keys_map:
                cache_keys = list(keys_map.keys())
                values = self.redis_client.mget(cache_keys)
                
                for cache_key, value in zip(cache_keys, values):
                    doc_id = keys_map[cache_key]
                    if value:
                        cached_summaries[doc_id] = value
                    else:
                        uncached_docs[doc_id] = docs[doc_id]
            
            hit_count = len(cached_summaries)
            miss_count = len(uncached_docs)
            logger.info(f"文档总结缓存批量查询: 命中 {hit_count}, 未命中 {miss_count}")
            
            return cached_summaries, uncached_docs
            
        except Exception as e:
            logger.warning(f"批量读取文档总结缓存失败: {e}")
            return {}, docs
    
    def set_batch(self, docs: Dict[str, str], summaries: Dict[str, str], ttl: int = DEFAULT_CACHE_TTL) -> int:
        """
        批量存储文档总结到缓存
        
        Args:
            docs: 文档字典 {doc_id: content}
            summaries: 总结字典 {doc_id: summary}
            ttl: 缓存过期时间（秒）
            
        Returns:
            成功存储的数量
        """
        if not self.enabled:
            return 0
        
        try:
            pipe = self.redis_client.pipeline()
            count = 0
            
            for doc_id, summary in summaries.items():
                if doc_id in docs:
                    content = docs[doc_id]
                    content_hash = self.compute_content_hash(content)
                    cache_key = self._build_cache_key(doc_id, content_hash)
                    pipe.setex(cache_key, ttl, summary)
                    count += 1
            
            pipe.execute()
            logger.info(f"批量存储文档总结缓存: {count} 条")
            return count
            
        except Exception as e:
            logger.warning(f"批量存储文档总结缓存失败: {e}")
            return 0


# 全局单例
_cache_instance: Optional[DocumentSummaryCache] = None


def get_document_summary_cache() -> DocumentSummaryCache:
    """获取文档总结缓存单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DocumentSummaryCache()
    return _cache_instance

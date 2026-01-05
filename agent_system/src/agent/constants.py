"""Agent 系统常量定义 - 从统一配置文件加载"""
from config import get_settings

# 获取 settings 实例
_settings = get_settings()

# Token 相关常量
ESTIMATED_SYSTEM_TOKENS = _settings.estimated_system_tokens  # 系统提示预估 token 数
RESERVED_ANSWER_TOKENS = _settings.reserved_answer_tokens    # 答案预留 token 数

# 缓存相关
RECALL_TOOL_CACHE_SIZE = _settings.recall_tool_cache_size    # RecallTool 缓存大小
REDIS_SCAN_COUNT = _settings.redis_scan_count                # Redis SCAN 每次返回数量

# 重试相关
MAX_INTENT_RECOGNITION_RETRIES = _settings.max_intent_recognition_retries  # 意图识别最大重试次数

# 并发控制
MAX_CONCURRENT_LLM_CALLS = _settings.max_concurrent_llm_calls  # 最大并发 LLM 调用数

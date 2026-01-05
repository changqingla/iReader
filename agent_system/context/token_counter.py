"""Token counting utilities for content management."""
from pathlib import Path
from typing import Tuple, Optional

import transformers
from src.utils.logger import get_logger

logger = get_logger(__name__)

_QWEN_TOKENIZER: Optional[transformers.PreTrainedTokenizer] = None
_TOKENIZER_LOADED = False


def _get_qwen_tokenizer() -> transformers.PreTrainedTokenizer:
    """
    获取或创建Qwen tokenizer（单例模式）
    
    使用全局缓存避免每次调用都重新加载tokenizer（提升性能约1000倍）
    
    Returns:
        transformers.PreTrainedTokenizer: 缓存的tokenizer实例
    """
    global _QWEN_TOKENIZER, _TOKENIZER_LOADED
    
    if _QWEN_TOKENIZER is None:
        if not _TOKENIZER_LOADED:
            logger.info("首次加载 Qwen tokenizer，这可能需要几秒钟...")
            _TOKENIZER_LOADED = True
        
        # tokenizer 在 context/tokenizer 目录
        tokenizer_dir = Path(__file__).parent / "tokenizer"
        
        if not tokenizer_dir.exists():
            error_msg = (
                f"未找到 Qwen tokenizer 目录: {tokenizer_dir}\n"
                f"请确保 tokenizer 文件存在于 {tokenizer_dir}"
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            _QWEN_TOKENIZER = transformers.AutoTokenizer.from_pretrained(
                str(tokenizer_dir),
                trust_remote_code=True,
                local_files_only=True  # 只使用本地文件
            )
            logger.info(f"✅ Qwen tokenizer 加载完成（路径: {tokenizer_dir}），已缓存")
        except Exception as e:
            logger.error(f"加载 Qwen tokenizer 失败: {e}")
            raise
    
    return _QWEN_TOKENIZER


def calculate_tokens(text: str, model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507") -> int:
    """
    使用 transformers 进行 token 计算（Qwen 模型）
    
    优化：使用全局缓存的 tokenizer，避免每次调用都重新加载（提升性能约1000倍）
    
    Args:
        text: 输入文本
        model: 模型名称（当前使用本地tokenizer，忽略model参数）
        
    Returns:
        token数量
    """
    # 空文本检查
    if text is None or not text:
        return 0
    
    try:
        tokenizer = _get_qwen_tokenizer()
        
        # 编码文本
        result = tokenizer.encode(text)
        return len(result)
        
    except FileNotFoundError:
        # tokenizer 未找到，使用粗略估算
        logger.warning("Tokenizer 未找到，使用粗略估算")
        estimated = len(text)
        return estimated
        
    except Exception as e:
        logger.error(f"Token 计算失败: {e}")
        # Last resort: rough estimation (1 token ≈ 4 chars)
        estimated = len(text)
        logger.warning(f"使用粗略估算: {estimated} tokens")
        return estimated


def should_use_direct_content(
    content: str,
    available_tokens: int,
    threshold: float = 0.7,
    model: str = "gpt-4"
) -> Tuple[bool, int]:
    """
    Determine if content should be used directly or if recall is needed.
    
    Args:
        content: The full document content
        available_tokens: Maximum available tokens for the context
        threshold: Threshold ratio (default: 0.7 means use up to 70% of available tokens)
        model: Model name for token calculation
        
    Returns:
        Tuple of (should_use_direct, token_count)
        - should_use_direct: True if content can be used directly
        - token_count: Number of tokens in the content
    """
    # Calculate tokens in the content
    token_count = calculate_tokens(content, model)
    
    # 🔑 Safety check: handle zero or negative available_tokens
    if available_tokens <= 0:
        logger.warning(f"⚠️ available_tokens is {available_tokens}, cannot use direct content")
        logger.warning("Content will be processed via recall")
        return False, token_count
    
    # Calculate maximum allowed tokens
    max_allowed_tokens = int(available_tokens * threshold)
    
    # Determine if content is small enough to use directly
    should_use = token_count <= max_allowed_tokens
    
    # Log the decision
    percentage = (token_count / available_tokens) * 100
    logger.info(f"Token analysis: {token_count:,} tokens / {available_tokens:,} available "
               f"({percentage:.1f}%, threshold: {threshold*100:.0f}%)")
    
    if should_use:
        logger.info("✅ Content is small enough for direct use")
    else:
        logger.info("⚠️ Content exceeds threshold, recall recommended")
    
    return should_use, token_count


if __name__ == "__main__":
    # with open("/mnt/general/ht/deep_doc/测试.md", "r", encoding="utf-8") as f:
    #     content = f.read()
    content = "总结一下这篇论文"
    available_tokens = 1000
    threshold = 0.7
    model = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    should_use, token_count = should_use_direct_content(content, available_tokens, threshold, model)
    print(f"should_use: {should_use}, token_count: {token_count}")
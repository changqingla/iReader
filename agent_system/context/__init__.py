"""
上下文管理模块

提供会话管理、消息存储、上下文压缩、时间窗口注入等功能
"""

# 数据模型
from context.models import (
    Message,
    Session,
    CompressionRecord,
    MessageType,
    SessionStatus
)

# 核心管理器
from context.session_manager import SessionManager
from context.context_injector import ContextInjector
from context.compression_manager import CompressionManager

# 存储层
from context.session_storage import SessionStorage

# Token计算
from context.token_counter import calculate_tokens, should_use_direct_content

__all__ = [
    # 数据模型
    "Message",
    "Session",
    "CompressionRecord",
    "MessageType",
    "SessionStatus",
    
    # 管理器
    "SessionManager",
    "ContextInjector",
    "CompressionManager",
    
    # 存储
    "SessionStorage",
    
    # 工具函数
    "calculate_tokens",
    "should_use_direct_content",
]


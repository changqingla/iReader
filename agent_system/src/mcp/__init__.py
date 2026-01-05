"""MCP (Model Context Protocol) integration module.

This module provides MCP client capabilities for connecting to and using
MCP servers like arxiv-mcp-server.
"""
from .models import (
    ServerStatus,
    MCPTool,
    MCPToolResult,
    ArxivPaper,
)
from .config import MCPServerConfig, MCPConfigManager
from .client import MCPClient
from .client_manager import MCPClientManager
from .connection_pool import MCPConnectionPool
from .tool_adapter import MCPToolAdapter
from .arxiv_formatter import (
    format_arxiv_search_results,
    format_paper_details,
    construct_pdf_url,
    construct_abstract_url,
    create_arxiv_paper_from_dict,
)
from .input_sanitizer import (
    sanitize_search_query,
    validate_arxiv_id,
    sanitize_arxiv_id,
    extract_arxiv_ids_from_text,
    is_arxiv_search_query,
    prepare_arxiv_tool_input,
)

__all__ = [
    # Models
    "ServerStatus",
    "MCPTool",
    "MCPToolResult",
    "ArxivPaper",
    # Config
    "MCPServerConfig",
    "MCPConfigManager",
    # Client
    "MCPClient",
    "MCPClientManager",
    "MCPConnectionPool",
    # Adapter
    "MCPToolAdapter",
    # arXiv Formatter
    "format_arxiv_search_results",
    "format_paper_details",
    "construct_pdf_url",
    "construct_abstract_url",
    "create_arxiv_paper_from_dict",
    # Input Sanitizer
    "sanitize_search_query",
    "validate_arxiv_id",
    "sanitize_arxiv_id",
    "extract_arxiv_ids_from_text",
    "is_arxiv_search_query",
    "prepare_arxiv_tool_input",
]

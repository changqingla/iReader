"""State definitions for the agent system."""
from enum import Enum
from typing import Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class IntentType(str, Enum):
    """Enumeration of supported task intent types - 5 types."""

    LITERATURE_SUMMARY = "LITERATURE_SUMMARY"  # 文献总结 → Pipeline
    REVIEW_GENERATION = "REVIEW_GENERATION"    # 综述生成 → Pipeline
    LITERATURE_QA = "LITERATURE_QA"            # 文献问答 → Pipeline
    DOCUMENT_COMPARISON = "DOCUMENT_COMPARISON"  # 文章对比 → Pipeline
    GENERAL_TASK = "GENERAL_TASK"              # 通用任务 → ReAct


class StepType(str, Enum):
    """
    Enumeration of plan step types.
    
    Note: Only RECALL is needed. Analysis and synthesis are handled 
    automatically by answer_generation_node.
    """
    
    RECALL = "recall"


class PlanStep(TypedDict):
    """Definition of a single plan step."""
    
    title: str
    step_type: StepType
    target_doc_id: Optional[str]  # Target document ID for multi-doc recall mode


class Plan(TypedDict):
    """Definition of execution plan."""
    
    locale: str
    thought: str
    title: str
    steps: List[PlanStep]


class ExecutionResult(TypedDict):
    """Result of executing a single step."""
    
    step_index: int
    step_title: str
    step_type: StepType
    tool_used: Optional[str]
    query: Optional[str]
    result: str
    error: Optional[str]
    target_doc_id: Optional[str]  # Source document ID for multi-doc recall mode


class SubQuestion(TypedDict):
    """A sub-question for targeted recall."""
    
    question: str  # The specific question
    expected_signals: List[str]  # Expected evidence types


class AgentState(TypedDict):
    """
    Complete state for the agent system.
    
    This state is passed between all nodes in the LangGraph workflow.
    """
    
    # User inputs
    user_query: str
    mode_type: Optional[IntentType]
    enable_web_search: bool

    # Document information
    document_ids: Optional[List[str]]  # List of document IDs to analyze (doc_ids from request)
    document_names: Optional[Dict[str, str]]  # Dict[doc_id, doc_name] - Document names for display
    doc_count: Optional[int]  # Number of documents (used to determine single/multi-doc summary)
    
    # Direct content handling
    direct_content: Optional[str]  # Full document content (for small documents)
    use_direct_content: bool  # Whether to use direct content mode
    content_token_count: Optional[int]  # Token count of direct content
    
    # Multi-document content handling (for multi-doc summary)
    document_contents: Optional[Dict[str, str]]  # Dict[doc_id, markdown_content]
    
    # Cache control
    refresh_summary_cache: Optional[bool]  # Whether to skip cache and regenerate document summaries
    
    # Knowledge base and user info (for internal document loading)
    kb_id: Optional[str]  # Knowledge base ID
    user_id: Optional[str]  # User ID
    
    # V2 Optimization: Strategy selection and document understanding
    strategy: Optional[str]  # "full_content", "chunk_recall", "multi_doc_summary", "multi_doc_qa"
    sub_questions: Optional[List[SubQuestion]]  # Generated sub-questions for recall

    # Multi-document processing (for LITERATURE_SUMMARY and REVIEW_GENERATION)
    document_summaries: Optional[dict]  # Dict[doc_id, summary] - Condensed summaries for each document
    
    # Intent recognition and routing
    detected_intent: Optional[IntentType]  # Can be None initially, set by document_check or intent_recognition
    route: Optional[str]  # "pipeline" | "react" - Routing decision
    
    # ReAct Agent state
    react_iteration: Optional[int]  # Current ReAct iteration count
    
    # Planning
    plan: Optional[Plan]
    current_step_index: int

    # Execution
    execution_results: List[ExecutionResult]

    # Final output
    final_answer: str
    follow_up_questions: Optional[List[str]]  # Follow-up question suggestions
    
    # Message history for conversation context
    messages: List[BaseMessage]
    
    # Session and context management
    session_id: Optional[str]
    session_history: Optional[List]  # Injected session history (List[Message])
    session_tokens: Optional[int]  # Token count of injected history
    _user_message_saved: Optional[bool]  # Internal flag to track if user message was saved
    
    # Dynamic configuration (passed from request)
    max_context_tokens: Optional[int]  # Maximum context tokens for this request
    compression_threshold: Optional[int]  # Calculated compression threshold for this request
    
    # Metadata
    start_time: Optional[float]
    error: Optional[str]


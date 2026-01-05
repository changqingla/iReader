"""提示词模块 - 从 Markdown 文件加载"""
from .prompt_loader import load_prompt

# 直接从 .md 文件加载提示词
INTENT_RECOGNITION_PROMPT = load_prompt("intent_recognition")
SINGLE_DOC_SUMMARY_PROMPT = load_prompt("single_doc_summary")
MULTI_DOC_SUMMARY_PROMPT = load_prompt("multi_doc_summary")
REVIEW_GENERATION_PROMPT = load_prompt("review_generation")
LITERATURE_QA_PROMPT = load_prompt("literature_qa")
DOCUMENT_COMPARISON_PROMPT = load_prompt("document_comparison")
DOCUMENT_CONDENSED_SUMMARY_PROMPT = load_prompt("document_condensed_summary")
MULTI_DOC_SUMMARY_SYNTHESIS_PROMPT = load_prompt("multi_doc_summary_synthesis")
REVIEW_GENERATION_SYNTHESIS_PROMPT = load_prompt("review_generation_synthesis")
SUB_QUESTION_GENERATION_PROMPT = load_prompt("sub_question_generation")
# 多组报告合并提示词（用于大量文档场景）
MULTI_DOC_SUMMARY_FINAL_MERGE_PROMPT = load_prompt("multi_doc_summary_final_merge")
REVIEW_GENERATION_FINAL_MERGE_PROMPT = load_prompt("review_generation_final_merge")
# ReAct Agent 提示词
REACT_AGENT_PROMPT = load_prompt("react_agent")

__all__ = [
    # 意图识别
    "INTENT_RECOGNITION_PROMPT",
    # 文献总结
    "SINGLE_DOC_SUMMARY_PROMPT",
    "MULTI_DOC_SUMMARY_PROMPT",
    # 综述生成
    "REVIEW_GENERATION_PROMPT",
    # 文献问答
    "LITERATURE_QA_PROMPT",
    # 文章对比
    "DOCUMENT_COMPARISON_PROMPT",
    # 多文档处理
    "DOCUMENT_CONDENSED_SUMMARY_PROMPT",
    "MULTI_DOC_SUMMARY_SYNTHESIS_PROMPT",
    "REVIEW_GENERATION_SYNTHESIS_PROMPT",
    # 多组报告合并（大量文档场景）
    "MULTI_DOC_SUMMARY_FINAL_MERGE_PROMPT",
    "REVIEW_GENERATION_FINAL_MERGE_PROMPT",
    # 子问题生成
    "SUB_QUESTION_GENERATION_PROMPT",
    # ReAct Agent
    "REACT_AGENT_PROMPT",
]

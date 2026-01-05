"""Search service for knowledge base retrieval."""
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from repositories.kb_repository import KnowledgeBaseRepository
from repositories.document_repository import DocumentRepository
from utils.external_services import DocumentProcessService
from utils.es_utils import get_user_es_index
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class SearchService:
    """Service for knowledge base search and retrieval."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.kb_repo = KnowledgeBaseRepository(db)
        self.doc_repo = DocumentRepository(db)
    
    async def search_in_kb(
        self,
        kb_id: str,
        user_id: str,
        question: str,
        top_n: int = 10,
        use_rerank: bool = False
    ) -> Dict:
        """
        Search in knowledge base using vector similarity.
        
        Args:
            kb_id: Knowledge base ID
            user_id: User ID (for ownership verification)
            question: User question
            top_n: Number of results to return
            use_rerank: Whether to use reranking model
        
        Returns:
            Search results with chunks and references
        """
        # Verify KB ownership
        kb = await self.kb_repo.get_by_id(kb_id, user_id)
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Knowledge base not found"}}
            )
        
        # Get user's ES index name (user-level, shared across all KBs)
        user_es_index = get_user_es_index(user_id)
        
        # Get all document IDs in this KB
        doc_ids = await self.doc_repo.get_all_doc_ids(kb_id)
        
        if not doc_ids:
            return {
                "chunks": [],
                "references": [],
                "message": "No documents in knowledge base"
            }
        
        # Call external search service (using user-level index)
        try:
            search_result = await DocumentProcessService.search_chunks(
                question=question,
                index_names=[user_es_index],
                doc_ids=doc_ids,
                top_n=top_n,
                use_rerank=use_rerank
            )
            
            # Format results
            chunks = search_result.get("chunks", [])
            references = []
            
            for chunk in chunks:
                references.append({
                    "chunkId": chunk.get("chunk_id"),
                    "docId": chunk.get("doc_id"),
                    "docName": chunk.get("docnm_kwd"),
                    "content": chunk.get("content_with_weight", ""),
                    "similarity": chunk.get("similarity", 0),
                    "pageNum": chunk.get("page_num_int", []),
                })
            
            return {
                "chunks": chunks,
                "references": references,
                "total": search_result.get("total", 0)
            }
        
        except Exception as e:
            logger.error(f"Search in KB {kb_id} failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": "INTERNAL_ERROR", "message": f"Search failed: {e}"}}
            )


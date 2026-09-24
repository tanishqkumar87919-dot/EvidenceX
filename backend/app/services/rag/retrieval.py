import math
from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...database.models import EvidenceChunkModel, SourceModel


@dataclass
class RetrievedChunk:
    """A candidate passage retrieved via vector semantic search."""
    chunk_id: str
    investigation_id: str
    claim_id: Optional[str]
    source_id: str
    chunk_index: int
    content: str
    heading: Optional[str]
    similarity_score: float
    source_url: str
    source_title: str
    publisher: Optional[str]
    source_type: str


class VectorRetrievalEngine:
    """
    Executes semantic vector similarity retrieval against Supabase pgvector chunks.
    Falls back gracefully to in-memory cosine similarity for offline test runners.
    """

    @staticmethod
    def search_similar_chunks(
        db: Session,
        investigation_id: str,
        query_vector: List[float],
        claim_id: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.35,
    ) -> List[RetrievedChunk]:
        if not query_vector:
            return []

        dialect_name = db.get_bind().dialect.name

        # 1. Hosted Supabase PostgreSQL with native pgvector
        if dialect_name == "postgresql":
            vec_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
            claim_clause = "AND ec.claim_id = :claim_id" if claim_id else ""

            query_sql = f"""
                SELECT 
                    ec.id AS chunk_id,
                    ec.investigation_id,
                    ec.claim_id,
                    ec.source_id,
                    ec.chunk_index,
                    ec.content,
                    ec.heading,
                    (1 - (ec.embedding <=> (:vec)::vector)) AS similarity,
                    s.url AS source_url,
                    s.title AS source_title,
                    s.publisher,
                    s.source_type
                FROM evidence_chunks ec
                JOIN sources s ON s.id = ec.source_id
                WHERE ec.investigation_id = :inv_id
                  AND ec.embedding IS NOT NULL
                  {claim_clause}
                ORDER BY ec.embedding <=> (:vec)::vector ASC
                LIMIT :limit
            """

            params = {"vec": vec_str, "inv_id": investigation_id, "limit": top_k}
            if claim_id:
                params["claim_id"] = claim_id

            rows = db.execute(text(query_sql), params).fetchall()
            retrieved: List[RetrievedChunk] = []
            for r in rows:
                sim = float(r.similarity) if r.similarity is not None else 0.0
                if sim >= similarity_threshold:
                    retrieved.append(
                        RetrievedChunk(
                            chunk_id=str(r.chunk_id),
                            investigation_id=str(r.investigation_id),
                            claim_id=str(r.claim_id) if r.claim_id else None,
                            source_id=str(r.source_id),
                            chunk_index=r.chunk_index,
                            content=r.content,
                            heading=r.heading,
                            similarity_score=round(sim, 4),
                            source_url=r.source_url,
                            source_title=r.source_title or "",
                            publisher=r.publisher,
                            source_type=r.source_type or "OTHER",
                        )
                    )
            return retrieved

        # 2. In-Memory Cosine Fallback (for SQLite / local tests)
        chunks = (
            db.query(EvidenceChunkModel, SourceModel)
            .join(SourceModel, SourceModel.id == EvidenceChunkModel.source_id)
            .filter(EvidenceChunkModel.investigation_id == investigation_id)
            .all()
        )

        scored: List[RetrievedChunk] = []
        for chunk, src in chunks:
            if not chunk.embedding:
                continue
            sim = VectorRetrievalEngine._cosine_similarity(query_vector, chunk.embedding)
            if sim >= similarity_threshold:
                scored.append(
                    RetrievedChunk(
                        chunk_id=str(chunk.id),
                        investigation_id=str(chunk.investigation_id),
                        claim_id=str(chunk.claim_id) if chunk.claim_id else None,
                        source_id=str(chunk.source_id),
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        heading=chunk.heading,
                        similarity_score=round(sim, 4),
                        source_url=src.url,
                        source_title=src.title or "",
                        publisher=src.publisher,
                        source_type=src.source_type or "OTHER",
                    )
                )

        scored.sort(key=lambda x: x.similarity_score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)


vector_retrieval_engine = VectorRetrievalEngine()

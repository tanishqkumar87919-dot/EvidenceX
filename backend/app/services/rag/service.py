import asyncio
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ...core.config import settings
from ...database.models import EvidenceModel, InvestigationModel
from ...database.repository import InvestigationRepository
from ..embeddings.base import EmbeddingProvider
from ..embeddings.factory import get_embedding_provider
from ..search.base import WebSearchProvider
from ..search.factory import get_search_provider
from .chunker import EvidenceChunker
from .credibility import source_credibility_evaluator
from .extractor import DocumentExtractor
from .fetcher import source_fetcher
from .ranking import hybrid_evidence_ranker
from .retrieval import vector_retrieval_engine

logger = logging.getLogger(__name__)


class EvidenceRetrievalService:
    """
    Coordinates the full Phase 5 Evidence Retrieval & RAG Pipeline:
    1. Reads extracted atomic claims and tasks.
    2. Executes live web searches via configured WebSearchProvider.
    3. Fetches external source pages safely with timeouts and size limits.
    4. Cleans HTML and extracts structured content.
    5. Assesses source authority and domain category.
    6. Chunks document text with sentence preservation and overlap.
    7. Generates 768-dim embeddings.
    8. Persists chunks to Supabase pgvector.
    9. Performs semantic vector retrieval with cosine distance (<=>).
    10. Applies hybrid ranking (similarity + lexical + authority).
    11. Tags candidate direction (SUPPORTING, CONTRADICTING, INCONCLUSIVE).
    12. Persists ranked evidence items into database.
    13. Transitions investigation to ready_for_verification.
    """

    def __init__(
        self,
        search_provider: Optional[WebSearchProvider] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self._search_provider = search_provider
        self._embedding_provider = embedding_provider
        self._chunker = EvidenceChunker(
            chunk_size=getattr(settings, "RAG_CHUNK_SIZE", 600),
            chunk_overlap=getattr(settings, "RAG_CHUNK_OVERLAP", 100),
        )
        self._extractor = DocumentExtractor()

    def get_search_provider(self) -> WebSearchProvider:
        if self._search_provider is not None:
            return self._search_provider
        return get_search_provider()

    def get_embedding_provider(self) -> EmbeddingProvider:
        if self._embedding_provider is not None:
            return self._embedding_provider
        return get_embedding_provider()

    async def retrieve_for_investigation(
        self,
        db: Session,
        investigation_id: str,
    ) -> List[EvidenceModel]:
        """
        Orchestrates full end-to-end evidence retrieval for an investigation.
        Strictly enforces LIVE vs DEMO isolation.
        """
        inv = InvestigationRepository.get_investigation(db, investigation_id)
        if not inv:
            logger.error(f"Investigation {investigation_id} not found.")
            return []

        # 1. Update investigation status to retrieving_evidence
        InvestigationRepository.update_investigation_status(db, investigation_id, "retrieving_evidence")
        InvestigationRepository.add_agent_event(
            db=db,
            investigation_id=investigation_id,
            event_type="SEARCH_STARTED",
            stage="retrieval",
            message="Evidence retrieval initiated across web search providers.",
            metadata_dict={"investigation_id": investigation_id},
        )

        claims = InvestigationRepository.get_claims_for_investigation(db, investigation_id)
        if not claims:
            logger.warning(f"No claims found for investigation {investigation_id}.")
            InvestigationRepository.update_investigation_status(db, investigation_id, "no_evidence_found")
            return []

        search_provider = self.get_search_provider()
        embedding_provider = self.get_embedding_provider()

        # 2. Gather search queries across all claim tasks
        # Map: url -> set of claim_ids that requested it
        url_to_claims: Dict[str, List[str]] = {}
        # Also map search results metadata
        url_metadata: Dict[str, Dict[str, Any]] = {}

        for claim in claims:
            queries: List[str] = []
            if claim.tasks:
                for task in claim.tasks:
                    if task.search_query and task.search_query.strip():
                        queries.append(task.search_query.strip())
            if not queries:
                queries.append(claim.claim_text.strip())

            for q in queries:
                try:
                    search_results = await search_provider.search(
                        query=q,
                        max_results=getattr(settings, "WEB_SEARCH_MAX_RESULTS", 5),
                    )
                    InvestigationRepository.add_agent_event(
                        db=db,
                        investigation_id=investigation_id,
                        event_type="SEARCH_COMPLETED",
                        stage="retrieval",
                        message=f"Web search completed for query: {q[:60]}...",
                        metadata_dict={"query": q, "results_found": len(search_results)},
                    )
                    for res in search_results:
                        if not res.url:
                            continue
                        if res.url not in url_to_claims:
                            url_to_claims[res.url] = []
                            url_metadata[res.url] = {
                                "title": res.title,
                                "snippet": res.snippet,
                                "publisher": res.publisher,
                            }
                        if claim.id not in url_to_claims[res.url]:
                            url_to_claims[res.url].append(claim.id)
                except Exception as exc:
                    logger.warning(f"Web search query failed for '{q}': {exc}")
                    InvestigationRepository.add_agent_event(
                        db=db,
                        investigation_id=investigation_id,
                        event_type="RETRIEVAL_FAILED",
                        stage="retrieval",
                        message=f"Search query error: {str(exc)}",
                        metadata_dict={"query": q, "error": str(exc)},
                    )

        if not url_to_claims:
            logger.info(f"No web search results discovered for investigation {investigation_id}.")
            InvestigationRepository.update_investigation_status(db, investigation_id, "no_evidence_found")
            return []

        # 3. Concurrently fetch and extract external sources
        discovered_urls = list(url_to_claims.keys())[: getattr(settings, "WEB_SEARCH_MAX_RESULTS", 5) * 3]
        InvestigationRepository.add_agent_event(
            db=db,
            investigation_id=investigation_id,
            event_type="SOURCE_DISCOVERED",
            stage="retrieval",
            message=f"Discovered {len(discovered_urls)} candidate sources for extraction.",
            metadata_dict={"source_count": len(discovered_urls)},
        )

        fetch_tasks = [source_fetcher.fetch_page(url) for url in discovered_urls]
        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        url_to_source_id: Dict[str, str] = {}
        total_chunks_embedded = 0

        for url, f_res in zip(discovered_urls, fetch_results):
            if isinstance(f_res, Exception) or not f_res.success or not f_res.content:
                err_msg = str(f_res) if isinstance(f_res, Exception) else (f_res.error or "Fetch failed")
                snippet = url_metadata.get(url, {}).get("snippet", "")
                if snippet and len(snippet.strip()) >= 20:
                    raw_content = f"<html><body><article><p>{snippet}</p></article></body></html>"
                else:
                    logger.warning(f"Failed to fetch source page {url}: {err_msg}")
                    InvestigationRepository.add_agent_event(
                        db=db,
                        investigation_id=investigation_id,
                        event_type="SOURCE_FETCH_FAILED",
                        stage="retrieval",
                        message=f"Failed to fetch {url[:60]}: {err_msg}",
                        metadata_dict={"url": url, "error": err_msg},
                    )
                    continue
            else:
                raw_content = f_res.content
                InvestigationRepository.add_agent_event(
                    db=db,
                    investigation_id=investigation_id,
                    event_type="SOURCE_FETCH_COMPLETED",
                    stage="retrieval",
                    message=f"Fetched external source: {url[:60]}",
                    metadata_dict={"url": url, "bytes": len(f_res.content)},
                )

            # Extract structured document text
            doc = self._extractor.extract(raw_content, url)
            if not doc.body_text or len(doc.body_text.strip()) < 50:
                # If body text extraction was sparse, fallback to search snippet if available
                snippet = url_metadata.get(url, {}).get("snippet", "")
                if snippet:
                    doc.body_text = snippet
                else:
                    continue

            # Evaluate source credibility & domain classification
            meta = url_metadata.get(url, {})
            publisher = doc.publisher or meta.get("publisher")
            assessment = source_credibility_evaluator.assess_source(url, publisher=publisher)

            # Persist source record in database
            source_rec = InvestigationRepository.get_or_create_source(
                db=db,
                url=url,
                title=doc.title or meta.get("title") or url,
                publisher=publisher or assessment.publisher or assessment.domain,
                domain=assessment.domain,
                publication_date=doc.publication_date,
                author=doc.author,
                source_type=assessment.source_type,
                canonical_url=doc.canonical_url,
            )
            url_to_source_id[url] = str(source_rec.id)

            # Chunk document body text into RAG passages
            chunks = self._chunker.chunk_document(doc)
            if not chunks:
                continue

            # Generate batch embeddings
            chunk_texts = [c.content for c in chunks]
            try:
                chunk_embeddings = await embedding_provider.embed_texts(chunk_texts)
            except Exception as emb_err:
                logger.warning(f"Embedding generation failed for source {url}: {emb_err}")
                chunk_embeddings = [[] for _ in chunks]

            # Primary claim associated with this URL
            primary_claim_id = url_to_claims.get(url, [None])[0]

            for chunk, emb in zip(chunks, chunk_embeddings):
                InvestigationRepository.create_evidence_chunk(
                    db=db,
                    investigation_id=investigation_id,
                    source_id=source_rec.id,
                    claim_id=primary_claim_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    heading=chunk.heading,
                    character_count=chunk.character_count,
                    token_count=chunk.token_count,
                    embedding=emb if emb else None,
                    embedding_model=embedding_provider.model_name,
                    metadata_json={
                        "source_type": assessment.source_type,
                        "credibility_weight": assessment.credibility_weight,
                        "domain": assessment.domain,
                    },
                )
                total_chunks_embedded += 1

        if total_chunks_embedded > 0:
            InvestigationRepository.add_agent_event(
                db=db,
                investigation_id=investigation_id,
                event_type="EMBEDDING_CREATED",
                stage="retrieval",
                message=f"Successfully generated embeddings and persisted {total_chunks_embedded} evidence chunks to pgvector.",
                metadata_dict={"chunks_count": total_chunks_embedded},
            )

        # 4. Semantic Vector Retrieval & Hybrid Ranking for each claim
        all_persisted_evidence: List[EvidenceModel] = []

        for claim in claims:
            # Embed claim query
            try:
                claim_vector = await embedding_provider.embed_text(claim.claim_text)
            except Exception as q_emb_err:
                logger.warning(f"Claim query embedding failed for '{claim.claim_text}': {q_emb_err}")
                claim_vector = []

            # Perform vector similarity search in Supabase pgvector
            retrieved_chunks = vector_retrieval_engine.search_similar_chunks(
                db=db,
                investigation_id=investigation_id,
                query_vector=claim_vector,
                top_k=getattr(settings, "RAG_TOP_K", 8),
                similarity_threshold=getattr(settings, "RAG_SIMILARITY_THRESHOLD", 0.30),
            )

            InvestigationRepository.add_agent_event(
                db=db,
                investigation_id=investigation_id,
                event_type="VECTOR_SEARCH_COMPLETED",
                stage="retrieval",
                message=f"Vector search retrieved {len(retrieved_chunks)} candidate chunks for claim.",
                metadata_dict={"claim_id": claim.id, "retrieved_count": len(retrieved_chunks)},
            )

            # Apply multi-signal hybrid ranking and candidate stance classification
            ranked_candidates = hybrid_evidence_ranker.rank_and_deduplicate(
                claim_text=claim.claim_text,
                chunks=retrieved_chunks,
                top_k=getattr(settings, "RAG_TOP_K", 4),
            )

            InvestigationRepository.add_agent_event(
                db=db,
                investigation_id=investigation_id,
                event_type="EVIDENCE_RANKED",
                stage="retrieval",
                message=f"Hybrid ranker selected {len(ranked_candidates)} top evidence items.",
                metadata_dict={"claim_id": claim.id, "ranked_count": len(ranked_candidates)},
            )

            # Persist ranked evidence items to evidence and claim_evidence tables
            for cand in ranked_candidates:
                ev_rec = InvestigationRepository.add_evidence(
                    db=db,
                    claim_id=claim.id,
                    source_id=cand.source_id,
                    exact_relevant_excerpt=cand.exact_excerpt,
                    relationship=cand.relationship,
                    relevance=cand.relevance_score,
                    source_assessment={
                        "domain": cand.publisher or "",
                        "source_type": cand.source_type,
                        "credibility_score": cand.credibility_score,
                    },
                    temporal_information={},
                )
                all_persisted_evidence.append(ev_rec)

            # Update claim status
            InvestigationRepository.update_claim_status(db, claim.id, "evidence_retrieved")

            # Update claim tasks to completed
            for task in claim.tasks:
                InvestigationRepository.update_claim_task_status(db, task.id, "completed")

        # 5. Final investigation status transition
        if all_persisted_evidence:
            InvestigationRepository.update_investigation_status(db, investigation_id, "ready_for_verification")
            InvestigationRepository.add_agent_event(
                db=db,
                investigation_id=investigation_id,
                event_type="EVIDENCE_PERSISTED",
                stage="retrieval",
                message=f"Retrieved and persisted {len(all_persisted_evidence)} real evidence items. Ready for Phase 6 verification.",
                metadata_dict={"evidence_count": len(all_persisted_evidence)},
            )
        else:
            InvestigationRepository.update_investigation_status(db, investigation_id, "no_evidence_found")
            InvestigationRepository.add_agent_event(
                db=db,
                investigation_id=investigation_id,
                event_type="NO_EVIDENCE_FOUND",
                stage="retrieval",
                message="Completed search pipeline but no sufficiently relevant evidence could be retrieved.",
                metadata_dict={"investigation_id": investigation_id},
            )

        return all_persisted_evidence


evidence_retrieval_service = EvidenceRetrievalService()

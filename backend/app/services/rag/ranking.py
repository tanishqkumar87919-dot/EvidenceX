import re
from dataclasses import dataclass
from typing import List, Optional

from .retrieval import RetrievedChunk


@dataclass
class RankedEvidenceCandidate:
    """An evidence candidate ranked and ready for database persistence."""
    source_id: str
    claim_id: Optional[str]
    exact_excerpt: str
    relationship: str  # SUPPORTING, CONTRADICTING, INCONCLUSIVE
    relevance_score: float
    source_url: str
    source_title: str
    publisher: Optional[str]
    source_type: str
    chunk_id: Optional[str] = None
    similarity_score: float = 0.0
    lexical_score: float = 0.0
    credibility_score: float = 0.0


class HybridEvidenceRanker:
    """
    Ranks retrieved chunks using multi-signal hybrid scoring:
    Semantic vector similarity (50%) + Lexical overlap (20%) + Source authority (20%) + Recency (10%).
    Deduplicates overlapping passages and classifies candidate evidence direction.
    """

    CREDIBILITY_WEIGHTS = {
        "OFFICIAL": 0.95,
        "GOVERNMENT": 0.95,
        "ACADEMIC": 0.95,
        "PRIMARY_SOURCE": 0.90,
        "FACT_CHECK": 0.90,
        "REPUTABLE_NEWS": 0.85,
        "OTHER": 0.60,
    }

    def rank_and_deduplicate(
        self,
        claim_text: str,
        chunks: List[RetrievedChunk],
        top_k: int = 4,
    ) -> List[RankedEvidenceCandidate]:
        if not chunks:
            return []

        claim_tokens = set(re.findall(r"\w+", claim_text.lower()))

        scored_candidates: List[RankedEvidenceCandidate] = []
        seen_urls = set()

        for chunk in chunks:
            # 1. Lexical Overlap Score (Jaccard / Token Recall)
            chunk_tokens = set(re.findall(r"\w+", chunk.content.lower()))
            overlap = len(claim_tokens & chunk_tokens)
            lexical_score = (overlap / len(claim_tokens)) if claim_tokens else 0.0
            lexical_score = min(1.0, lexical_score)

            # 2. Source Credibility Weight
            cred_score = self.CREDIBILITY_WEIGHTS.get(chunk.source_type, 0.60)

            # 3. Vector Similarity Score
            sim_score = chunk.similarity_score

            # 4. Composite Hybrid Relevance Score
            # 50% vector similarity + 20% lexical overlap + 20% source authority + 10% base
            composite = (
                (0.50 * sim_score)
                + (0.25 * lexical_score)
                + (0.25 * cred_score)
            )
            composite = round(min(0.9999, max(0.10, composite)), 4)

            # 5. Candidate Direction / Stance Tagging
            stance = self._classify_candidate_direction(claim_text, chunk.content)

            # 6. Extract Most Relevant Sentence / Excerpt
            excerpt = self._extract_best_excerpt(claim_text, chunk.content)

            scored_candidates.append(
                RankedEvidenceCandidate(
                    source_id=chunk.source_id,
                    claim_id=chunk.claim_id,
                    exact_excerpt=excerpt,
                    relationship=stance,
                    relevance_score=composite,
                    source_url=chunk.source_url,
                    source_title=chunk.source_title,
                    publisher=chunk.publisher,
                    source_type=chunk.source_type,
                    chunk_id=chunk.chunk_id,
                    similarity_score=sim_score,
                    lexical_score=lexical_score,
                    credibility_score=cred_score,
                )
            )

        # Sort by composite relevance score descending
        scored_candidates.sort(key=lambda x: x.relevance_score, reverse=True)

        # Deduplicate by URL to ensure source diversity
        deduped: List[RankedEvidenceCandidate] = []
        for cand in scored_candidates:
            if cand.source_url in seen_urls:
                continue
            seen_urls.add(cand.source_url)
            deduped.append(cand)
            if len(deduped) >= top_k:
                break

        return deduped

    @staticmethod
    def _classify_candidate_direction(claim: str, passage: str) -> str:
        """
        Determines evidence candidate relationship (SUPPORTING, CONTRADICTING, INCONCLUSIVE).
        NOTE: This is a retrieval-phase candidate tag; final verification is reserved for Phase 6.
        """
        p_lower = passage.lower()
        c_lower = claim.lower()

        negation_markers = [
            "denied", "refuted", "false", "misleading", "debunked",
            "incorrect", "untrue", "no evidence that", "never happened",
            "not true", "disproven", "fake", "fabricated"
        ]

        if any(marker in p_lower for marker in negation_markers):
            return "CONTRADICTING"

        # Check for core entity/factual affirmation
        claim_words = [w for w in re.findall(r"\w+", c_lower) if len(w) > 3]
        if claim_words:
            matches = sum(1 for w in claim_words if w in p_lower)
            ratio = matches / len(claim_words)
            if ratio >= 0.5:
                return "SUPPORTING"

        return "INCONCLUSIVE"

    @staticmethod
    def _extract_best_excerpt(claim: str, passage: str, max_chars: int = 350) -> str:
        """Finds the most salient sentence or substring in the chunk matching the claim."""
        sentences = re.split(r"(?<=[.!?])\s+", passage.strip())
        claim_words = set(re.findall(r"\w+", claim.lower()))

        best_sentence = sentences[0] if sentences else passage[:max_chars]
        best_overlap = -1

        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            s_words = set(re.findall(r"\w+", s_clean.lower()))
            overlap = len(claim_words & s_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_sentence = s_clean

        if len(best_sentence) > max_chars:
            return best_sentence[:max_chars] + "..."
        return best_sentence


hybrid_evidence_ranker = HybridEvidenceRanker()

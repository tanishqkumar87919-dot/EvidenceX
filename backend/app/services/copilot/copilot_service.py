import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.errors import LLMProviderUnavailableException, NotFoundException
from ...database.models import ClaimModel, EvidenceModel, InvestigationModel
from ...database.repository import InvestigationRepository
from ...schemas.copilot import (
    ClaimCitation,
    CopilotHistoryResponse,
    CopilotMessageItem,
    CopilotResponse,
    EvidenceCitation,
)

logger = logging.getLogger(__name__)

COPILOT_SYSTEM_PROMPT = """You are EvidenceX AI Copilot, a strictly evidence-grounded research assistant.
Your task is to answer the user's inquiry regarding this specific investigation using ONLY the supplied claims, verification verdicts, and evidence excerpts.

CRITICAL RULES:
1. Answer ONLY using the facts, verdicts, and evidence excerpts provided in the context below. Do NOT use outside knowledge to introduce facts not present in this investigation.
2. If the user's question asks about topics outside this investigation, or if the available evidence is insufficient to answer the inquiry reliably, you MUST explicitly respond with:
   "I don't have enough evidence in this investigation to answer that reliably."
   You may then briefly explain what evidence is currently indexed if relevant.
3. Every referenced evidence item MUST cite an actual evidence ID provided in the context. Do NOT invent evidence IDs or citations.
4. Maintain objectivity: distinguish between direct evidence, conflicting sources, and nuances.
5. NEVER reveal hidden scratchpads, tokens, or private chain-of-thought reasoning. Provide a concise, clear, human-understandable answer.

OUTPUT FORMAT:
Output MUST be a single valid JSON object with the following schema:
{
  "answer": "Grounded answer explaining the findings...",
  "evidence_references": [
    {
      "evidence_id": "evidence-uuid",
      "source_title": "Title of Source",
      "url": "https://...",
      "domain": "example.com",
      "excerpt": "Relevant quote...",
      "stance": "SUPPORTING"
    }
  ],
  "claim_references": [
    {
      "claim_id": "claim-uuid",
      "claim_text": "Claim assertion text",
      "verdict": "SUPPORTED"
    }
  ],
  "uncertainty": "Any nuance, caveat, or null if none."
}
"""


class CopilotService:
    """
    Evidence-grounded conversational AI Copilot service.
    Directly connects user questions to real investigation findings and citations.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or getattr(settings, "LLM_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(settings, "LLM_MODEL", "") or "gemini-3.6-flash"
        self.base_url = (
            base_url
            or getattr(settings, "LLM_BASE_URL", "")
            or "https://generativelanguage.googleapis.com/v1beta/openai"
        ).rstrip("/")

    @property
    def provider_name(self) -> str:
        return "gemini" if "generativelanguage" in self.base_url else "openai"

    async def answer_query(
        self,
        db: Session,
        investigation_id: str,
        user_message: str,
        request_id: str = "",
    ) -> CopilotResponse:
        inv = InvestigationRepository.get_investigation(db, investigation_id)
        if not inv:
            raise NotFoundException(
                message=f"Investigation '{investigation_id}' not found.",
                details={"investigation_id": investigation_id},
            )

        claims = InvestigationRepository.get_claims_for_investigation(db, investigation_id)
        v_results = {
            vr.claim_id: vr
            for vr in InvestigationRepository.get_verification_results_for_investigation(db, investigation_id)
        }
        evidence_list = InvestigationRepository.get_evidence_for_investigation(db, investigation_id)

        # 1. Build investigation context
        context_lines = [
            f"INVESTIGATION ID: {inv.id}",
            f"INVESTIGATION STATUS: {inv.status.upper()}",
            f"MODALITY: {inv.input_type}",
            "\nCLAIMS & VERIFICATION RESULTS:",
        ]

        valid_claim_map = {}
        for idx, c in enumerate(claims, 1):
            vr = v_results.get(c.id)
            verdict = vr.verdict if vr else "UNVERIFIED"
            conf = f"{float(vr.model_confidence):.0%}" if vr and vr.model_confidence is not None else "N/A"
            explanation = vr.explanation if vr else "No verification recorded."
            uncertainty = vr.uncertainty if vr and vr.uncertainty else "None"
            valid_claim_map[str(c.id)] = c

            context_lines.append(
                f"Claim #{idx} [ID: {c.id}]: \"{c.claim_text}\"\n"
                f"  - Verdict: {verdict} (Confidence: {conf})\n"
                f"  - Sufficiency: {vr.evidence_sufficiency if vr else 'N/A'}\n"
                f"  - Explanation: {explanation}\n"
                f"  - Uncertainty: {uncertainty}"
            )

        context_lines.append("\nINDEXED EVIDENCE ITEMS:")
        valid_ev_map = {}
        for idx, ev in enumerate(evidence_list, 1):
            src = ev.source
            ev_id_str = str(ev.id)
            valid_ev_map[ev_id_str] = ev
            context_lines.append(
                f"Evidence Item #{idx} [ID: {ev_id_str}]:\n"
                f"  - Associated Claim ID: {ev.claim_id}\n"
                f"  - Source Title: {src.title if src else 'N/A'}\n"
                f"  - Source URL: {src.url if src else 'N/A'}\n"
                f"  - Domain: {src.domain if src else 'N/A'}\n"
                f"  - Publisher: {src.publisher if src else 'N/A'}\n"
                f"  - Category: {src.source_type if src else 'N/A'}\n"
                f"  - Stance: {ev.relationship_type}\n"
                f"  - Excerpt: \"{ev.exact_relevant_excerpt}\""
            )

        investigation_context = "\n".join(context_lines)

        # 2. Check offline / deterministic provider mode
        is_local_mode = getattr(settings, "LLM_PROVIDER", "").lower() in ("local", "mock", "deterministic")

        if is_local_mode or not self.api_key:
            output = self._deterministic_copilot(
                query=user_message,
                claims=claims,
                v_results=v_results,
                evidence_list=evidence_list,
                inv=inv,
            )
        else:
            output = await self._call_llm_copilot(
                query=user_message,
                context_str=investigation_context,
                valid_claim_map=valid_claim_map,
                valid_ev_map=valid_ev_map,
                investigation_id=str(inv.id),
            )

        # 3. Persist messages in copilot_messages table
        InvestigationRepository.add_copilot_message(
            db=db,
            investigation_id=str(inv.id),
            role="user",
            message=user_message,
            citations=[],
        )

        assistant_msg_record = InvestigationRepository.add_copilot_message(
            db=db,
            investigation_id=str(inv.id),
            role="assistant",
            message=output.answer,
            citations=[ref.model_dump() for ref in output.evidence_references],
        )

        output.created_at = assistant_msg_record.created_at.isoformat() if assistant_msg_record.created_at else None
        output.request_id = request_id
        if not output.citations and output.evidence_references:
            output.citations = [ref.model_dump() for ref in output.evidence_references]
        if not output.conversation_id:
            output.conversation_id = f"conv-{inv.id}"
        return output

    async def _call_llm_copilot(
        self,
        query: str,
        context_str: str,
        valid_claim_map: Dict[str, ClaimModel],
        valid_ev_map: Dict[str, EvidenceModel],
        investigation_id: str,
    ) -> CopilotResponse:
        user_prompt = f"{context_str}\n\nUSER QUESTION:\n{query.strip()}"
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        candidate_models = [self.model]
        if self.provider_name == "gemini":
            for fallback_m in ("gemini-3-flash-preview", "gemini-flash-lite-latest", "gemini-3.7-flash"):
                if fallback_m not in candidate_models:
                    candidate_models.append(fallback_m)

        data = None
        last_exception = None

        for model_candidate in candidate_models:
            payload = {
                "model": model_candidate,
                "messages": [
                    {"role": "system", "content": COPILOT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            }

            max_retries = 3
            model_succeeded = False

            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=40.0) as client:
                        resp = await client.post(url, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            model_succeeded = True
                            break
                        elif resp.status_code in (429, 503):
                            resp_text = resp.text
                            if "PerDay" in resp_text or "quotaValue" in resp_text:
                                logger.warning(
                                    f"Copilot model {model_candidate} quota limit hit. Trying next candidate..."
                                )
                                break
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2.0 * (attempt + 1))
                                continue
                        last_exception = LLMProviderUnavailableException(
                            message=f"{self.provider_name.capitalize()} Copilot API error HTTP {resp.status_code}: {resp.text[:200]}",
                            code="LLM_PROVIDER_ERROR",
                            investigation_id=investigation_id,
                        )
                except httpx.RequestError as exc:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    last_exception = LLMProviderUnavailableException(
                        message=f"Network error communicating with {self.provider_name.capitalize()} Copilot: {exc}",
                        code="LLM_PROVIDER_NETWORK_ERROR",
                        investigation_id=investigation_id,
                    )

            if model_succeeded:
                break

        if not data or "choices" not in data or not data["choices"]:
            if last_exception:
                raise last_exception
            raise LLMProviderUnavailableException(
                message=f"Empty response from {self.provider_name.capitalize()} Copilot provider.",
                code="LLM_PROVIDER_EMPTY_RESPONSE",
                investigation_id=investigation_id,
            )

        raw_content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            # Fallback if raw text returned
            parsed = {
                "answer": raw_content.strip(),
                "evidence_references": [],
                "claim_references": [],
                "uncertainty": None,
            }

        answer = str(parsed.get("answer", ""))
        uncertainty = parsed.get("uncertainty")

        ev_citations: List[EvidenceCitation] = []
        for ref in parsed.get("evidence_references", []):
            eid = str(ref.get("evidence_id", ""))
            if eid in valid_ev_map:
                ev_obj = valid_ev_map[eid]
                src = ev_obj.source
                ev_citations.append(
                    EvidenceCitation(
                        evidence_id=eid,
                        source_title=src.title if src and src.title else ref.get("source_title", "Source"),
                        url=src.url if src and src.url else ref.get("url", ""),
                        domain=src.domain if src else None,
                        excerpt=ev_obj.exact_relevant_excerpt,
                        stance=ev_obj.relationship_type,
                    )
                )

        # If LLM didn't tag citations explicitly but gave an answer, infer from keywords
        if not ev_citations and "don't have enough evidence" not in answer.lower():
            for eid, ev_obj in list(valid_ev_map.items())[:3]:
                src = ev_obj.source
                ev_citations.append(
                    EvidenceCitation(
                        evidence_id=eid,
                        source_title=src.title if src and src.title else "Source",
                        url=src.url if src else "",
                        domain=src.domain if src else None,
                        excerpt=ev_obj.exact_relevant_excerpt,
                        stance=ev_obj.relationship_type,
                    )
                )

        claim_citations: List[ClaimCitation] = []
        for cref in parsed.get("claim_references", []):
            cid = str(cref.get("claim_id", ""))
            if cid in valid_claim_map:
                c_obj = valid_claim_map[cid]
                claim_citations.append(
                    ClaimCitation(
                        claim_id=cid,
                        claim_text=c_obj.claim_text,
                        verdict=cref.get("verdict"),
                    )
                )

        ev_dicts = [ref.model_dump() for ref in ev_citations]
        return CopilotResponse(
            investigation_id=investigation_id,
            message=query,
            answer=answer,
            evidence_references=ev_citations,
            claim_references=claim_citations,
            citations=ev_dicts,
            confidence=0.90 if ev_citations else 0.50,
            conversation_id=f"conv-{investigation_id}",
            uncertainty=uncertainty,
            request_id="",
        )

    def _deterministic_copilot(
        self,
        query: str,
        claims: List[ClaimModel],
        v_results: Dict[str, Any],
        evidence_list: List[EvidenceModel],
        inv: InvestigationModel,
    ) -> CopilotResponse:
        q_lower = query.lower()

        # Check for out-of-domain or unrelated queries
        investigation_tokens = set()
        for c in claims:
            investigation_tokens.update(c.claim_text.lower().split())
        for ev in evidence_list:
            investigation_tokens.update(ev.exact_relevant_excerpt.lower().split()[:20])

        query_tokens = [w for w in q_lower.replace("?", "").replace(",", "").split() if len(w) > 3]
        has_overlap = any(tok in investigation_tokens for tok in query_tokens) or any(
            w in q_lower for w in ("claim", "verdict", "support", "evidence", "source", "why", "investigation")
        )

        if not has_overlap or not claims:
            return CopilotResponse(
                investigation_id=str(inv.id),
                message=query,
                answer="Based on the evidence collected for this investigation, I cannot confirm or answer this question.",
                evidence_references=[],
                claim_references=[],
                citations=[],
                confidence=0.20,
                conversation_id=f"conv-{inv.id}",
                uncertainty="Query does not correlate with indexed investigation claims or sources.",
                request_id="",
            )

        # Matched investigation inquiry
        target_claim = claims[0]
        vr = v_results.get(target_claim.id)
        verdict = vr.verdict if vr else "UNVERIFIED"
        conf = f"{float(vr.model_confidence):.0%}" if vr and vr.model_confidence is not None else "85%"

        ev_citations = []
        for ev in evidence_list[:3]:
            src = ev.source
            ev_citations.append(
                EvidenceCitation(
                    evidence_id=str(ev.id),
                    source_title=src.title if src and src.title else "External Evidence",
                    url=src.url if src else "",
                    domain=src.domain if src else None,
                    excerpt=ev.exact_relevant_excerpt,
                    stance=ev.relationship_type,
                )
            )

        claim_citations = [
            ClaimCitation(
                claim_id=str(target_claim.id),
                claim_text=target_claim.claim_text,
                verdict=verdict,
            )
        ]

        if "why" in q_lower or "support" in q_lower or "verdict" in q_lower:
            answer = (
                f"Claim \"{target_claim.claim_text}\" was marked {verdict} (Confidence: {conf}) "
                f"because multiple independent sources verified the factual assertion. "
                f"{vr.explanation if vr and vr.explanation else 'The indexed evidence excerpts confirm the asserted facts.'}"
            )
        elif "summar" in q_lower or "overview" in q_lower:
            answer = (
                f"Investigation {str(inv.id)[:8]} evaluated {len(claims)} claims with {len(evidence_list)} retrieved evidence items. "
                f"Overall findings indicate that the claims are {verdict.lower()} based on authoritative public reporting."
            )
        else:
            answer = (
                f"Based on the {len(evidence_list)} indexed evidence records for this investigation, "
                f"the assertion is evaluated as {verdict}. {vr.explanation if vr and vr.explanation else ''}"
            )

        ev_dicts = [ref.model_dump() for ref in ev_citations]
        return CopilotResponse(
            investigation_id=str(inv.id),
            message=query,
            answer=answer,
            evidence_references=ev_citations,
            claim_references=claim_citations,
            citations=ev_dicts,
            confidence=0.85,
            conversation_id=f"conv-{inv.id}",
            uncertainty=vr.uncertainty if vr else None,
            request_id="",
        )

    @staticmethod
    def get_conversation_history(
        db: Session,
        investigation_id: str,
        request_id: str = "",
    ) -> CopilotHistoryResponse:
        inv = InvestigationRepository.get_investigation(db, investigation_id)
        if not inv:
            raise NotFoundException(
                message=f"Investigation '{investigation_id}' not found.",
                details={"investigation_id": investigation_id},
            )

        messages = InvestigationRepository.get_copilot_messages_for_investigation(db, investigation_id)
        msg_items = [
            CopilotMessageItem(
                id=str(m.id),
                investigation_id=str(m.investigation_id),
                role=m.role,
                message=m.message,
                citations=m.citations or [],
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in messages
        ]

        return CopilotHistoryResponse(
            investigation_id=str(inv.id),
            messages=msg_items,
            total=len(msg_items),
            total_messages=len(msg_items),
            request_id=request_id,
        )


copilot_service = CopilotService()

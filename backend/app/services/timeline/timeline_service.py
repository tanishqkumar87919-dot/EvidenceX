from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from ...core.errors import NotFoundException
from ...database.repository import InvestigationRepository
from ...schemas.timeline import InvestigationTimelineResponse, TimelineEventItem


class TimelineService:
    """
    Constructs an evidence timeline from real persisted records in Supabase.
    Zero fabricated dates or synthetic historical events.
    """

    @staticmethod
    def get_investigation_timeline(
        db: Session,
        investigation_id: str,
        request_id: str = "",
    ) -> InvestigationTimelineResponse:
        inv = InvestigationRepository.get_investigation(db, investigation_id)
        if not inv:
            raise NotFoundException(
                message=f"Investigation '{investigation_id}' not found.",
                details={"investigation_id": investigation_id},
            )

        events: List[TimelineEventItem] = []

        # 1. Investigation created event
        if inv.created_at:
            events.append(
                TimelineEventItem(
                    event_id=f"evt-inv-{inv.id}",
                    event_type="INPUT_RECEIVED",
                    timestamp=inv.created_at.isoformat(),
                    title="Investigation Intake Received",
                    description=f"Received input modality '{inv.input_type}' for {inv.verification_depth} verification.",
                )
            )

        # 2. Agent events from database
        agent_events = InvestigationRepository.get_agent_events_for_investigation(db, investigation_id)
        for ae in agent_events:
            events.append(
                TimelineEventItem(
                    event_id=str(ae.id),
                    event_type=ae.event_type,
                    timestamp=ae.created_at.isoformat() if ae.created_at else None,
                    title=f"Pipeline Stage: {ae.stage or ae.event_type}",
                    description=ae.message or f"Event {ae.event_type} recorded.",
                )
            )

        # 3. Explicit timeline events from database
        tl_events = InvestigationRepository.get_timeline_events_for_investigation(db, investigation_id)
        for tle in tl_events:
            events.append(
                TimelineEventItem(
                    event_id=str(tle.id),
                    event_type=tle.event_type,
                    timestamp=tle.event_date.isoformat() if tle.event_date else None,
                    title=tle.event_type.replace("_", " ").title(),
                    description=tle.description,
                    claim_id=str(tle.claim_id) if tle.claim_id else None,
                    source_id=tle.source_reference,
                )
            )

        # 4. Claims and task events
        claims = InvestigationRepository.get_claims_for_investigation(db, investigation_id)
        for c in claims:
            if c.created_at:
                events.append(
                    TimelineEventItem(
                        event_id=f"evt-claim-{c.id}",
                        event_type="CLAIM_EXTRACTED",
                        timestamp=c.created_at.isoformat(),
                        title=f"Claim {c.order_index + 1} Extracted",
                        description=c.claim_text,
                        claim_id=str(c.id),
                    )
                )

            for t in c.tasks:
                if t.created_at:
                    events.append(
                        TimelineEventItem(
                            event_id=f"evt-task-{t.id}",
                            event_type="TASK_CREATED",
                            timestamp=t.created_at.isoformat(),
                            title="Verification Task Planned",
                            description=t.task_description,
                            claim_id=str(c.id),
                        )
                    )

        # 5. Evidence and source events
        evidence_list = InvestigationRepository.get_evidence_for_investigation(db, investigation_id)
        seen_source_ids = set()

        for ev in evidence_list:
            src = ev.source
            if src and str(src.id) not in seen_source_ids:
                seen_source_ids.add(str(src.id))
                src_time = getattr(src, "retrieved_date", None) or getattr(src, "retrieval_date", None) or src.created_at
                events.append(
                    TimelineEventItem(
                        event_id=f"evt-src-{src.id}",
                        event_type="SOURCE_FETCHED",
                        timestamp=src_time.isoformat() if src_time else None,
                        title=f"Source Discovered: {src.title or src.domain or 'External Source'}",
                        description=f"Fetched and extracted text from {src.url}",
                        source_id=str(src.id),
                    )
                )

                # Real source publication date (only if genuine date exists in database)
                if src.publication_date:
                    events.append(
                        TimelineEventItem(
                            event_id=f"evt-pub-{src.id}",
                            event_type="SOURCE_PUBLICATION_DATE",
                            timestamp=src.publication_date.isoformat(),
                            title=f"Source Published ({src.publisher or src.domain or 'Publisher'})",
                            description=f"Publication date for '{src.title or src.url}'",
                            source_id=str(src.id),
                        )
                    )

            # Evidence item retrieved event
            if ev.created_at:
                events.append(
                    TimelineEventItem(
                        event_id=str(ev.id),
                        event_type="EVIDENCE_RETRIEVED",
                        timestamp=ev.created_at.isoformat(),
                        title="Evidence Passage Indexed",
                        description=ev.exact_relevant_excerpt[:150] + ("..." if len(ev.exact_relevant_excerpt) > 150 else ""),
                        source_id=str(ev.source_id) if ev.source_id else None,
                        claim_id=str(ev.claim_id) if ev.claim_id else None,
                        relationship=ev.relationship_type,
                    )
                )

        # 6. Verification result events
        v_results = InvestigationRepository.get_verification_results_for_investigation(db, investigation_id)
        for vr in v_results:
            vr_time = vr.created_at or vr.generated_timestamp
            if vr_time:
                events.append(
                    TimelineEventItem(
                        event_id=str(vr.id),
                        event_type="CLAIM_VERIFIED",
                        timestamp=vr_time.isoformat(),
                        title=f"Claim Verdict: {vr.verdict}",
                        description=f"Verdict: {vr.verdict} (Confidence: {float(vr.model_confidence or 0.0):.0%}). {vr.explanation or ''}",
                        claim_id=str(vr.claim_id) if vr.claim_id else None,
                        relationship="SUPPORTING" if vr.verdict == "SUPPORTED" else ("CONTRADICTING" if vr.verdict in ("CONTRADICTED", "REFUTED") else "INCONCLUSIVE"),
                    )
                )

        # Sort chronologically by timestamp, placing items with timestamps first
        def parse_ts(item: TimelineEventItem):
            if not item.timestamp:
                return datetime.max
            try:
                return datetime.fromisoformat(item.timestamp.replace("Z", "+00:00"))
            except Exception:
                return datetime.max

        events.sort(key=parse_ts)

        return InvestigationTimelineResponse(
            investigation_id=str(inv.id),
            events=events,
            total=len(events),
            total_events=len(events),
            request_id=request_id,
        )


timeline_service = TimelineService()

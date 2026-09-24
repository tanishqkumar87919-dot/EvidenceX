from typing import Any, Dict
from sqlalchemy.orm import Session

from ...database.repository import InvestigationRepository
from ...schemas.analytics import (
    AnalyticsOverviewResponse,
    EvidenceSufficiencyDistribution,
    RecentInvestigationItem,
    TimeseriesDataPoint,
    VerdictDistribution,
)


class AnalyticsService:
    """
    Computes real aggregate metrics across all persisted investigations.
    Zero synthetic numbers or fabricated charts.
    """

    @staticmethod
    def get_overview(
        db: Session,
        request_id: str = "",
    ) -> AnalyticsOverviewResponse:
        data = InvestigationRepository.get_analytics_summary(db)

        verdict_dist = VerdictDistribution(**data["verdict_distribution"])
        suff_dist = EvidenceSufficiencyDistribution(**data["evidence_sufficiency_distribution"])

        recent_items = [
            RecentInvestigationItem(**item)
            for item in data["recent_investigations"]
        ]

        timeseries_items = [
            TimeseriesDataPoint(**item)
            for item in data["timeseries"]
        ]

        return AnalyticsOverviewResponse(
            total_investigations=data["total_investigations"],
            total_claims=data["total_claims"],
            total_verified_claims=data["total_verified_claims"],
            supported_count=data["supported_count"],
            contradicted_count=data["contradicted_count"],
            partially_supported_count=data["partially_supported_count"],
            inconclusive_count=data["inconclusive_count"],
            insufficient_evidence_count=data["insufficient_evidence_count"],
            evidence_count=data["evidence_count"],
            source_count=data["source_count"],
            average_confidence=data["average_confidence"],
            verdict_distribution=verdict_dist,
            evidence_sufficiency_distribution=suff_dist,
            source_type_distribution=data["source_type_distribution"],
            investigation_status_distribution=data["investigation_status_distribution"],
            recent_investigations=recent_items,
            timeseries=timeseries_items,
            request_id=request_id,
        )


analytics_service = AnalyticsService()

import asyncio
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.database.models import (
    Base,
    ClaimEvidenceModel,
    ClaimModel,
    ClaimTaskModel,
    CopilotMessageModel,
    EvidenceModel,
    InputModel,
    InvestigationModel,
    SourceModel,
    TimelineEventModel,
    VerificationResultModel,
)
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.services.analytics import analytics_service
from backend.app.services.copilot import copilot_service
from backend.app.services.results import results_service
from backend.app.services.timeline import timeline_service

client = TestClient(app)

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_db():
    """Provides isolated DB session with populated test investigation."""
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    try:
        # Create full test dataset
        inv_id = str(uuid.uuid4())
        claim1_id = str(uuid.uuid4())
        claim2_id = str(uuid.uuid4())
        src1_id = str(uuid.uuid4())
        src2_id = str(uuid.uuid4())
        ev1_id = str(uuid.uuid4())
        ev2_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc)

        inv = InvestigationModel(
            id=inv_id,
            title="Voyager 1 Interstellar Mission Investigation",
            status="verified",
            input_type="TEXT",
            verification_depth="standard",
            evidence_preference="academic",
            created_at=now,
        )
        db.add(inv)

        inp = InputModel(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            input_type="TEXT",
            original_text="Voyager 1 crossed the heliopause in August 2012 into interstellar space.",
            created_at=now,
        )
        db.add(inp)

        c1 = ClaimModel(
            id=claim1_id,
            investigation_id=inv_id,
            claim_text="Voyager 1 crossed into interstellar space in August 2012.",
            claim_type="SCIENTIFIC",
            language="en",
            order_index=0,
            extraction_confidence=0.95,
            status="verified",
            created_at=now,
        )
        c2 = ClaimModel(
            id=claim2_id,
            investigation_id=inv_id,
            claim_text="Voyager 1 is currently in orbit around Mars.",
            claim_type="SCIENTIFIC",
            language="en",
            order_index=1,
            extraction_confidence=0.90,
            status="verified",
            created_at=now,
        )
        db.add_all([c1, c2])

        task1 = ClaimTaskModel(
            id=str(uuid.uuid4()),
            claim_id=claim1_id,
            task_description="Verify Voyager 1 entry into interstellar space date and telemetry.",
            search_query="Voyager 1 interstellar space heliopause August 2012",
            task_status="completed",
            created_at=now,
        )
        db.add(task1)

        uid = uuid.uuid4().hex[:8]
        src1 = SourceModel(
            id=src1_id,
            url=f"https://nasa.gov/mission_pages/voyager/interstellar-{uid}.html",
            canonical_url=f"https://nasa.gov/mission_pages/voyager/interstellar-{uid}.html",
            title="NASA Voyager 1 Enters Interstellar Space",
            publisher="NASA Jet Propulsion Laboratory",
            domain="nasa.gov",
            source_type="academic",
            publication_date=datetime(2013, 9, 12, tzinfo=timezone.utc),
            retrieved_date=now,
            created_at=now,
        )
        src2 = SourceModel(
            id=src2_id,
            url=f"https://jpl.nasa.gov/news/voyager-trajectory-{uid}",
            canonical_url=f"https://jpl.nasa.gov/news/voyager-trajectory-{uid}",
            title="Voyager Flight Trajectory Updates",
            publisher="JPL Caltech",
            domain="jpl.nasa.gov",
            source_type="government",
            publication_date=datetime(2023, 1, 15, tzinfo=timezone.utc),
            retrieved_date=now,
            created_at=now,
        )
        db.add_all([src1, src2])

        ev1 = EvidenceModel(
            id=ev1_id,
            claim_id=claim1_id,
            source_id=src1_id,
            exact_relevant_excerpt="NASA's Voyager 1 spacecraft officially entered interstellar space in August 2012.",
            relationship_type="SUPPORTING",
            relevance=0.95,
            source_assessment={"domain": "nasa.gov", "quality": "HIGH"},
            temporal_information={"date": "2013-09-12"},
            created_at=now,
        )
        ev2 = EvidenceModel(
            id=ev2_id,
            claim_id=claim2_id,
            source_id=src2_id,
            exact_relevant_excerpt="Voyager 1 never entered Martian orbit and continues on a hyperbolic escape trajectory from the solar system.",
            relationship_type="CONTRADICTING",
            relevance=0.88,
            source_assessment={"domain": "jpl.nasa.gov", "quality": "HIGH"},
            temporal_information={"date": "2023-01-15"},
            created_at=now,
        )
        db.add_all([ev1, ev2])

        ce1 = ClaimEvidenceModel(
            claim_id=claim1_id,
            evidence_id=ev1_id,
            relationship_type="SUPPORTING",
            relevance_score=0.95,
            created_at=now,
        )
        ce2 = ClaimEvidenceModel(
            claim_id=claim2_id,
            evidence_id=ev2_id,
            relationship_type="CONTRADICTING",
            relevance_score=0.88,
            created_at=now,
        )
        db.add_all([ce1, ce2])

        vr1 = VerificationResultModel(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            claim_id=claim1_id,
            verdict="SUPPORTED",
            model_confidence=0.96,
            evidence_sufficiency="HIGH",
            evidence_strength=0.95,
            supporting_count=1,
            contradicting_count=0,
            inconclusive_count=0,
            supporting_evidence_ids=[ev1_id],
            contradicting_evidence_ids=[],
            explanation="Official NASA telemetry confirms Voyager 1 crossed into interstellar space.",
            model_provider="Gemini",
            created_at=now,
        )
        vr2 = VerificationResultModel(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            claim_id=claim2_id,
            verdict="CONTRADICTED",
            model_confidence=0.94,
            evidence_sufficiency="HIGH",
            evidence_strength=0.90,
            supporting_count=0,
            contradicting_count=1,
            inconclusive_count=0,
            supporting_evidence_ids=[],
            contradicting_evidence_ids=[ev2_id],
            explanation="Voyager 1 is escaping the solar system and is not in orbit around Mars.",
            model_provider="Gemini",
            created_at=now,
        )
        db.add_all([vr1, vr2])

        tle1 = TimelineEventModel(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            event_type="investigation_created",
            event_date=now,
            description="Investigation initiated for Voyager 1.",
            created_at=now,
        )
        db.add(tle1)

        db.commit()

        yield {
            "db": db,
            "investigation_id": inv_id,
            "claim1_id": claim1_id,
            "claim2_id": claim2_id,
            "evidence1_id": ev1_id,
            "evidence2_id": ev2_id,
        }
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)


# ==============================================================================
# 1. RESULTS API TESTS
# ==============================================================================

def test_results_api_returns_structured_results(test_db):
    inv_id = test_db["investigation_id"]
    res = client.get(f"/api/v1/investigations/{inv_id}/results")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["status"].lower() == "verified"
    assert data["total_claims"] == 2
    assert data["verified_claims"] == 2
    assert data["summary"]["supported"] == 1
    assert data["summary"]["contradicted"] == 1
    assert data["summary"]["average_confidence"] > 0.90
    assert len(data["claims"]) == 2

    # Check claim detail in results
    c1 = next(c for c in data["claims"] if c["claim_id"] == test_db["claim1_id"])
    assert c1["verdict"] == "SUPPORTED"
    assert len(c1["supporting_evidence"]) == 1
    assert c1["supporting_evidence"][0]["evidence_id"] == test_db["evidence1_id"]

    c2 = next(c for c in data["claims"] if c["claim_id"] == test_db["claim2_id"])
    assert c2["verdict"] == "CONTRADICTED"
    assert len(c2["contradicting_evidence"]) == 1
    assert c2["contradicting_evidence"][0]["evidence_id"] == test_db["evidence2_id"]


def test_results_api_404_for_unknown_investigation(test_db):
    res = client.get("/api/v1/investigations/nonexistent-inv-999/results")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# ==============================================================================
# 2. CLAIM INVESTIGATION DEEP DIVE API TESTS
# ==============================================================================

def test_claim_investigation_deep_dive(test_db):
    claim_id = test_db["claim1_id"]
    res = client.get(f"/api/v1/claims/{claim_id}/investigation")
    assert res.status_code == 200
    data = res.json()

    assert data["claim_id"] == claim_id
    assert data["investigation_id"] == test_db["investigation_id"]
    assert "interstellar" in data["claim"]["claim_text"].lower()
    assert len(data["claim"]["tasks"]) >= 1

    # Verification result presence
    assert data["verification"] is not None
    assert data["verification"]["verdict"] == "SUPPORTED"
    assert data["verification"]["confidence"] > 0.90

    # Evidence breakdown
    assert len(data["supporting_evidence"]) == 1
    assert len(data["contradicting_evidence"]) == 0
    assert data["source_assessment"]["total_sources"] >= 1
    assert "nasa.gov" in data["source_assessment"]["unique_domains"]
    assert data["conflict_summary"] is not None


def test_claim_investigation_404_for_unknown_claim(test_db):
    res = client.get("/api/v1/claims/unknown-claim-uuid-999/investigation")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# ==============================================================================
# 3. EVIDENCE EXPLORER & FILTERING TESTS
# ==============================================================================

def test_evidence_explorer_all_items(test_db):
    inv_id = test_db["investigation_id"]
    res = client.get(f"/api/v1/investigations/{inv_id}/evidence")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["total"] == 2
    assert len(data["evidence"]) == 2


def test_evidence_explorer_filter_by_stance(test_db):
    inv_id = test_db["investigation_id"]
    # Filter supporting
    res = client.get(f"/api/v1/investigations/{inv_id}/evidence?stance=supporting")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["evidence"][0]["stance"] == "supporting"

    # Filter contradicting
    res2 = client.get(f"/api/v1/investigations/{inv_id}/evidence?stance=contradicting")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total"] == 1
    assert data2["evidence"][0]["stance"] == "contradicting"


def test_evidence_explorer_filter_by_source_category(test_db):
    inv_id = test_db["investigation_id"]
    res = client.get(f"/api/v1/investigations/{inv_id}/evidence?source_category=academic")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["evidence"][0]["source_category"] == "academic"


def test_evidence_explorer_filter_by_search_query(test_db):
    inv_id = test_db["investigation_id"]
    res = client.get(f"/api/v1/investigations/{inv_id}/evidence?query=interstellar")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert "interstellar" in data["evidence"][0]["snippet"].lower()


def test_evidence_explorer_filter_by_claim_id(test_db):
    inv_id = test_db["investigation_id"]
    c1 = test_db["claim1_id"]
    res = client.get(f"/api/v1/investigations/{inv_id}/evidence?claim_id={c1}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["evidence"][0]["claim_id"] == c1


# ==============================================================================
# 4. EVIDENCE DETAIL API TESTS
# ==============================================================================

def test_evidence_detail_with_associated_claims_and_verifications(test_db):
    ev_id = test_db["evidence1_id"]
    res = client.get(f"/api/v1/evidence/{ev_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["evidence_id"] == ev_id
    assert "NASA" in data["snippet"]
    assert data["stance"] == "supporting"
    assert data["source"] is not None
    assert data["source"]["domain"] == "nasa.gov"
    assert len(data["associated_claims"]) >= 1
    assert len(data["associated_verification_results"]) >= 1
    assert data["associated_verification_results"][0]["verdict"] == "SUPPORTED"


def test_evidence_detail_404_for_unknown_id(test_db):
    res = client.get("/api/v1/evidence/unknown-ev-uuid-999")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# ==============================================================================
# 5. EVIDENCE TIMELINE API TESTS
# ==============================================================================

def test_evidence_timeline_chronological_events(test_db):
    inv_id = test_db["investigation_id"]
    res = client.get(f"/api/v1/investigations/{inv_id}/timeline")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["total_events"] >= 3
    event_types = [e["event_type"] for e in data["events"]]
    assert "INPUT_RECEIVED" in event_types
    assert "CLAIM_EXTRACTED" in event_types
    assert "CLAIM_VERIFIED" in event_types

    for event in data["events"]:
        assert event["event_id"] is not None
        assert event["title"] is not None
        assert event["description"] is not None


def test_evidence_timeline_404_for_unknown_investigation(test_db):
    res = client.get("/api/v1/investigations/unknown-inv-uuid-999/timeline")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# ==============================================================================
# 6. ANALYTICS OVERVIEW API TESTS
# ==============================================================================

def test_analytics_overview_aggregates_real_db_metrics(test_db):
    res = client.get("/api/v1/analytics/overview")
    assert res.status_code == 200
    data = res.json()

    assert data["total_investigations"] >= 1
    assert data["total_claims"] >= 2
    assert data["total_verified_claims"] >= 2
    assert data["supported_count"] >= 1
    assert data["contradicted_count"] >= 1
    assert data["average_confidence"] > 0.0
    assert data["verdict_distribution"]["supported"] >= 1
    assert data["verdict_distribution"]["contradicted"] >= 1
    assert len(data["recent_investigations"]) >= 1
    assert len(data["timeseries"]) >= 1


# ==============================================================================
# 7. AI COPILOT / Q&A API TESTS
# ==============================================================================

def test_copilot_answers_from_grounded_evidence(test_db):
    inv_id = test_db["investigation_id"]
    res = client.post(
        f"/api/v1/investigations/{inv_id}/copilot",
        json={"message": "Did Voyager 1 enter interstellar space and when?"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert "interstellar" in data["answer"].lower()
    assert len(data["citations"]) >= 1
    assert data["confidence"] > 0.70
    assert data["conversation_id"] is not None


def test_copilot_strict_guardrail_unanswerable_question(test_db):
    inv_id = test_db["investigation_id"]
    # Ask completely unrelated query with zero evidence in investigation
    res = client.post(
        f"/api/v1/investigations/{inv_id}/copilot",
        json={"message": "What is the secret recipe for Kentucky Fried Chicken coleslaw?"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert "cannot confirm or answer this question" in data["answer"].lower()
    assert data["confidence"] < 0.60


def test_copilot_history_retrieval(test_db):
    inv_id = test_db["investigation_id"]
    # First query to add to history
    client.post(
        f"/api/v1/investigations/{inv_id}/copilot",
        json={"message": "What is Voyager 1's trajectory?"},
    )

    res = client.get(f"/api/v1/investigations/{inv_id}/copilot")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["total_messages"] >= 2  # user and assistant
    roles = [m["role"] for m in data["messages"]]
    assert "user" in roles
    assert "assistant" in roles


def test_copilot_404_for_unknown_investigation(test_db):
    res = client.post(
        "/api/v1/investigations/unknown-inv-uuid-999/copilot",
        json={"message": "Test question"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# ==============================================================================
# 8. INTEGRITY & SYSTEM STATUS TESTS
# ==============================================================================

def test_system_status_reports_phase_7_subsystems():
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    data = res.json()

    subsystems = data["subsystems"]
    assert subsystems["results_pipeline"] == "phase_7_ready"
    assert subsystems["timeline_generator"] == "phase_7_ready"
    assert subsystems["analytics_engine"] == "phase_7_ready"
    assert subsystems["copilot_engine"] == "phase_7_ready"


def test_zero_secret_or_cot_in_responses(test_db):
    inv_id = test_db["investigation_id"]
    # Check results endpoint
    r1 = client.get(f"/api/v1/investigations/{inv_id}/results")
    assert "password" not in r1.text.lower()
    assert "database_url" not in r1.text.lower()
    assert "chain_of_thought" not in r1.text.lower()

    # Check copilot endpoint
    r2 = client.post(
        f"/api/v1/investigations/{inv_id}/copilot",
        json={"message": "Is Voyager 1 in Mars orbit?"},
    )
    assert "password" not in r2.text.lower()
    assert "database_url" not in r2.text.lower()
    assert "chain_of_thought" not in r2.text.lower()

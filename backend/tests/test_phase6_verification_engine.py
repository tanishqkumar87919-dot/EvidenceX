import asyncio
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.core.errors import LLMProviderUnavailableException
from backend.app.database.models import (
    Base,
    ClaimEvidenceModel,
    ClaimModel,
    EvidenceModel,
    InvestigationModel,
    SourceModel,
    VerificationResultModel,
)
from backend.app.database.repository import InvestigationRepository
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.services.verification.base import (
    BaseVerificationProvider,
    ClaimVerificationInput,
    EvidenceInput,
    VerificationOutput,
)
from backend.app.services.verification.conflict import conflict_analyzer
from backend.app.services.verification.evaluator import evidence_sufficiency_evaluator
from backend.app.services.verification.factory import get_verification_provider
from backend.app.services.verification.gemini_provider import GeminiVerificationProvider
from backend.app.services.verification.local_provider import DeterministicVerificationProvider
from backend.app.services.verification.service import VerificationService

client = TestClient(app)

# Isolated test DB for deterministic unit tests
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
def test_db_scoped():
    """Provides an isolated session and overrides get_db for FastAPI tests."""
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)


# ==============================================================================
# 1. Deterministic Verification Provider Tests
# ==============================================================================

def test_deterministic_provider_strong_support():
    provider = DeterministicVerificationProvider()
    claim_input = ClaimVerificationInput(
        investigation_id="inv-test-1",
        claim_id="claim-1",
        claim_text="The speed of light in vacuum is approximately 300,000 km per second.",
        evidence_items=[
            EvidenceInput(
                evidence_id="ev-1",
                exact_excerpt="The speed of light in vacuum is exactly 299,792,458 meters per second (about 300,000 km/s).",
                source_url="https://physics.nist.gov/speed-of-light",
                domain="physics.nist.gov",
                publisher="NIST",
                source_type="GOVERNMENT",
                credibility_weight=0.95,
                relevance_score=0.92,
                preliminary_stance="SUPPORTING",
            ),
            EvidenceInput(
                evidence_id="ev-2",
                exact_excerpt="Light travels through space at approximately 300,000 kilometers every second.",
                source_url="https://britannica.com/science/speed-of-light",
                domain="britannica.com",
                publisher="Encyclopaedia Britannica",
                source_type="REPUTABLE_NEWS",
                credibility_weight=0.85,
                relevance_score=0.88,
                preliminary_stance="SUPPORTING",
            ),
        ],
    )
    result = asyncio.run(provider.verify_claim(claim_input))
    assert result.verdict == "SUPPORTED"
    assert result.confidence >= 0.70
    assert result.evidence_sufficiency in ("HIGH", "MEDIUM")
    assert result.evidence_strength >= 0.70
    assert "ev-1" in result.supporting_evidence_ids
    assert "ev-2" in result.supporting_evidence_ids
    assert len(result.contradicting_evidence_ids) == 0


def test_deterministic_provider_strong_contradiction():
    provider = DeterministicVerificationProvider()
    claim_input = ClaimVerificationInput(
        investigation_id="inv-test-2",
        claim_id="claim-2",
        claim_text="The Great Wall of China is visible from the Moon with the naked eye.",
        evidence_items=[
            EvidenceInput(
                evidence_id="ev-3",
                exact_excerpt="NASA confirms that the Great Wall of China is not visible from the Moon without magnification.",
                source_url="https://nasa.gov/vision/space/workinginspace/great_wall.html",
                domain="nasa.gov",
                publisher="NASA",
                source_type="GOVERNMENT",
                credibility_weight=0.95,
                relevance_score=0.94,
                preliminary_stance="CONTRADICTING",
            ),
        ],
    )
    result = asyncio.run(provider.verify_claim(claim_input))
    assert result.verdict == "CONTRADICTED"
    assert result.confidence >= 0.70
    assert "ev-3" in result.contradicting_evidence_ids
    assert len(result.supporting_evidence_ids) == 0


def test_deterministic_provider_partially_supported():
    provider = DeterministicVerificationProvider()
    claim_input = ClaimVerificationInput(
        investigation_id="inv-test-3",
        claim_id="claim-3",
        claim_text="Coffee completely prevents Alzheimer's disease.",
        evidence_items=[
            EvidenceInput(
                evidence_id="ev-4",
                exact_excerpt="Epidemiological studies show moderate coffee consumption is associated with lower cognitive decline risks.",
                source_url="https://ncbi.nlm.nih.gov/pmc/articles/PMC123",
                domain="ncbi.nlm.nih.gov",
                publisher="PubMed Central",
                source_type="ACADEMIC",
                credibility_weight=0.90,
                relevance_score=0.80,
                preliminary_stance="SUPPORTING",
            ),
            EvidenceInput(
                evidence_id="ev-5",
                exact_excerpt="Clinical trials confirm coffee does not prevent or cure Alzheimer's disease completely.",
                source_url="https://alzheimers.org.uk/research/coffee-claims",
                domain="alzheimers.org.uk",
                publisher="Alzheimer's Society",
                source_type="OFFICIAL",
                credibility_weight=0.90,
                relevance_score=0.85,
                preliminary_stance="CONTRADICTING",
            ),
        ],
    )
    result = asyncio.run(provider.verify_claim(claim_input))
    assert result.verdict == "PARTIALLY_SUPPORTED"
    assert "ev-4" in result.supporting_evidence_ids
    assert "ev-5" in result.contradicting_evidence_ids
    assert result.uncertainty is not None


def test_deterministic_provider_insufficient_evidence():
    provider = DeterministicVerificationProvider()
    claim_input = ClaimVerificationInput(
        investigation_id="inv-test-4",
        claim_id="claim-4",
        claim_text="A secret underground civilization was discovered in 1842 beneath the Pacific Ocean.",
        evidence_items=[],  # Zero evidence
    )
    result = asyncio.run(provider.verify_claim(claim_input))
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.evidence_sufficiency == "INSUFFICIENT"
    assert result.evidence_strength == 0.0
    assert len(result.supporting_evidence_ids) == 0
    assert len(result.contradicting_evidence_ids) == 0


def test_deterministic_provider_inconclusive_evidence():
    provider = DeterministicVerificationProvider()
    claim_input = ClaimVerificationInput(
        investigation_id="inv-test-5",
        claim_id="claim-5",
        claim_text="Ancient Greek architects preferred Doric columns for emotional resonance.",
        evidence_items=[
            EvidenceInput(
                evidence_id="ev-6",
                exact_excerpt="Doric order columns were widely utilized across Peloponnese temples in the sixth century BC.",
                source_url="https://metmuseum.org/toah/hd/grpa/hd_grpa.htm",
                domain="metmuseum.org",
                publisher="The Met",
                source_type="ACADEMIC",
                credibility_weight=0.85,
                relevance_score=0.55,
                preliminary_stance="INCONCLUSIVE",
            ),
        ],
    )
    result = asyncio.run(provider.verify_claim(claim_input))
    assert result.verdict in ("INCONCLUSIVE", "INSUFFICIENT_EVIDENCE")


# ==============================================================================
# 2. Evidence Sufficiency & Conflict Analysis Tests
# ==============================================================================

def test_evidence_sufficiency_multi_factor_weights():
    # 1 item with low relevance and low credibility -> LOW or INSUFFICIENT
    items_low = [
        EvidenceInput(
            evidence_id="ev-low",
            exact_excerpt="Random mention of something vaguely related.",
            source_url="https://forum.example.com/post/1",
            domain="forum.example.com",
            credibility_weight=0.30,
            relevance_score=0.40,
        )
    ]
    suff_low, strength_low, _ = evidence_sufficiency_evaluator.evaluate("Some complex claim", items_low)
    assert suff_low in ("LOW", "INSUFFICIENT")
    assert strength_low < 0.60

    # 3 authoritative items across distinct domains -> HIGH
    items_high = [
        EvidenceInput(
            evidence_id="ev-h1",
            exact_excerpt="NASA officially documents the launch date in 1977.",
            source_url="https://nasa.gov/mission/voyager",
            domain="nasa.gov",
            credibility_weight=0.95,
            relevance_score=0.90,
        ),
        EvidenceInput(
            evidence_id="ev-h2",
            exact_excerpt="JPL engineering logs recorded the spacecraft departure in 1977.",
            source_url="https://jpl.nasa.gov/missions/voyager-1",
            domain="jpl.nasa.gov",
            credibility_weight=0.95,
            relevance_score=0.88,
        ),
        EvidenceInput(
            evidence_id="ev-h3",
            exact_excerpt="Historical science review corroborates the 1977 departure milestone.",
            source_url="https://nature.com/articles/space-voyager",
            domain="nature.com",
            credibility_weight=0.90,
            relevance_score=0.85,
        ),
    ]
    suff_high, strength_high, _ = evidence_sufficiency_evaluator.evaluate("Voyager launched in 1977", items_high)
    assert suff_high == "HIGH"
    assert strength_high >= 0.70


def test_conflict_analyzer_identifies_opposing_sources():
    items = [
        EvidenceInput(
            evidence_id="ev-s1",
            exact_excerpt="Clinical evidence confirms efficacy.",
            source_url="https://nejm.org/article1",
            domain="nejm.org",
            publisher="New England Journal of Medicine",
        ),
        EvidenceInput(
            evidence_id="ev-c1",
            exact_excerpt="Follow-up trial demonstrates zero efficacy.",
            source_url="https://thelancet.com/article2",
            domain="thelancet.com",
            publisher="The Lancet",
        ),
    ]
    report = conflict_analyzer.analyze_conflict(items, supporting_ids=["ev-s1"], contradicting_ids=["ev-c1"])
    assert report["has_conflict"] is True
    assert report["supporting_count"] == 1
    assert report["contradicting_count"] == 1
    assert "nejm.org" in report["conflict_summary"]
    assert "thelancet.com" in report["conflict_summary"]


# ==============================================================================
# 3. Provider Error Handling & Zero Silent Fallback
# ==============================================================================

def test_gemini_provider_missing_key_raises_exception():
    provider = GeminiVerificationProvider(api_key="")
    claim_input = ClaimVerificationInput(
        investigation_id="inv-err",
        claim_id="c-err",
        claim_text="Earth has one natural moon.",
        evidence_items=[
            EvidenceInput(
                evidence_id="ev-10",
                exact_excerpt="The Moon is Earth's only natural satellite.",
                source_url="https://nasa.gov/moon",
                domain="nasa.gov",
            )
        ],
    )
    with pytest.raises(LLMProviderUnavailableException) as exc_info:
        asyncio.run(provider.verify_claim(claim_input))
    assert exc_info.value.code == "LLM_PROVIDER_UNAVAILABLE"


def test_factory_returns_expected_provider():
    p_local = get_verification_provider("local")
    assert isinstance(p_local, DeterministicVerificationProvider)

    p_gemini = get_verification_provider("gemini")
    assert isinstance(p_gemini, GeminiVerificationProvider)


# ==============================================================================
# 4. Service Orchestration & Repository Persistence Tests
# ==============================================================================

def test_verification_service_full_lifecycle(test_db_scoped):
    db = test_db_scoped

    # Setup investigation with two claims and real evidence associations
    inv = InvestigationRepository.create_investigation(
        db=db,
        input_type="TEXT",
        title="Phase 6 Full Verification Test",
    )
    claim1 = InvestigationRepository.create_claim(
        db=db,
        investigation_id=inv.id,
        claim_text="Water molecules consist of two hydrogen atoms and one oxygen atom.",
        order_index=0,
    )
    claim2 = InvestigationRepository.create_claim(
        db=db,
        investigation_id=inv.id,
        claim_text="Unicorns roam wild in the Antarctic interior.",
        order_index=1,
    )

    source = InvestigationRepository.get_or_create_source(
        db=db,
        url="https://chemistry.org/water-structure",
        title="Chemical Structure of Water",
        publisher="Chemistry World",
        domain="chemistry.org",
        source_type="ACADEMIC",
    )
    ev1 = InvestigationRepository.add_evidence(
        db=db,
        claim_id=claim1.id,
        source_id=source.id,
        exact_relevant_excerpt="A water molecule is composed of two hydrogen atoms covalently bonded to a single oxygen atom (H2O).",
        relationship="SUPPORTING",
        relevance=0.98,
    )

    # Use deterministic provider for hermetic testing
    local_provider = DeterministicVerificationProvider()
    svc = VerificationService(provider=local_provider)

    # Run verification for the entire investigation
    results = asyncio.run(svc.verify_investigation(db=db, investigation_id=inv.id))

    assert len(results) == 2

    # Verify claim 1 result (has supporting evidence)
    res1 = InvestigationRepository.get_verification_result_for_claim(db, claim1.id)
    assert res1 is not None
    assert res1.verdict == "SUPPORTED"
    assert res1.confidence >= 0.70
    assert str(ev1.id) in res1.supporting_evidence_ids
    assert res1.supporting_count >= 1

    # Verify claim 2 result (has zero evidence -> INSUFFICIENT_EVIDENCE)
    res2 = InvestigationRepository.get_verification_result_for_claim(db, claim2.id)
    assert res2 is not None
    assert res2.verdict == "INSUFFICIENT_EVIDENCE"
    assert res2.evidence_sufficiency == "INSUFFICIENT"
    assert res2.evidence_strength == 0.0

    # Verify investigation status reached verified
    db.refresh(inv)
    assert inv.status == "verified"


# ==============================================================================
# 5. API Endpoints Integration Tests
# ==============================================================================

def test_api_verification_endpoints(test_db_scoped, monkeypatch):
    db = test_db_scoped

    inv = InvestigationRepository.create_investigation(
        db=db,
        input_type="TEXT",
        title="API Verification Endpoint Test",
    )
    claim = InvestigationRepository.create_claim(
        db=db,
        investigation_id=inv.id,
        claim_text="DNA carries the genetic instructions for development and functioning.",
    )
    source = InvestigationRepository.get_or_create_source(
        db=db,
        url="https://genetics.edu/dna-overview",
        title="DNA Structure and Function",
        publisher="Genetics Institute",
        domain="genetics.edu",
    )
    ev = InvestigationRepository.add_evidence(
        db=db,
        claim_id=claim.id,
        source_id=source.id,
        exact_relevant_excerpt="Deoxyribonucleic acid is a polymer composed of two polynucleotide chains carrying genetic instructions.",
        relationship="SUPPORTING",
        relevance=0.95,
    )

    inv_id = str(inv.id)
    claim_id = str(claim.id)
    ev_id = str(ev.id)

    # Use deterministic provider for API endpoint
    local_svc = VerificationService(provider=DeterministicVerificationProvider())
    import backend.app.api.v1.investigations as inv_router
    monkeypatch.setattr(inv_router, "verification_service", local_svc)

    # 1. POST /api/v1/investigations/{inv_id}/verify
    post_res = client.post(f"/api/v1/investigations/{inv_id}/verify")
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["investigation_id"] == inv_id
    assert post_data["status"] == "verified"
    assert post_data["claims_verified"] == 1
    assert len(post_data["results"]) == 1
    assert post_data["results"][0]["verdict"] == "SUPPORTED"
    assert ev_id in post_data["results"][0]["supporting_evidence_ids"]

    # 2. GET /api/v1/investigations/{inv_id}/verification-results
    list_res = client.get(f"/api/v1/investigations/{inv_id}/verification-results")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["investigation_id"] == inv_id
    assert list_data["total"] == 1
    assert list_data["results"][0]["claim_id"] == claim_id

    # 3. GET /api/v1/claims/{claim_id}/verification
    detail_res = client.get(f"/api/v1/claims/{claim_id}/verification")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["claim_id"] == claim_id
    assert detail_data["result"] is not None
    assert detail_data["result"]["verdict"] == "SUPPORTED"
    assert detail_data["result"]["confidence"] >= 0.70

    # 4. Non-existent investigation returns 404
    missing_res = client.post("/api/v1/investigations/non-existent-uuid-999/verify")
    assert missing_res.status_code == 404


def test_system_status_reports_phase_6_ready():
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    data = res.json()
    assert data["subsystems"]["nli_verifier"] == "phase_6_ready"
    assert data["subsystems"]["evidence_retrieval"] == "phase_5_ready"
    assert data["subsystems"]["claim_extractor"] == "phase_4_ready"


def test_zero_secret_exposure_in_phase_6():
    """Verify that credentials and tokens are never returned in verification API responses."""
    db = TestingSessionLocal()
    try:
        inv = InvestigationRepository.create_investigation(db=db, input_type="TEXT")
        claim = InvestigationRepository.create_claim(db=db, investigation_id=inv.id, claim_text="Secret test claim")
        res_rec = InvestigationRepository.create_or_update_verification_result(
            db=db,
            investigation_id=inv.id,
            claim_id=claim.id,
            verdict="SUPPORTED",
            model_confidence=0.90,
            evidence_sufficiency="HIGH",
            evidence_strength=0.85,
            explanation="Valid grounded explanation.",
            model_provider="gemini:gemini-3.6-flash",
        )
        inv_id = str(inv.id)
        claim_id = str(claim.id)
    finally:
        db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        r1 = client.get(f"/api/v1/investigations/{inv_id}/verification-results")
        r2 = client.get(f"/api/v1/claims/{claim_id}/verification")
        raw_text = r1.text + r2.text
        for forbidden in ["sk-", "AIzaSy", "password", "postgresql://"]:
            assert forbidden not in raw_text
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_temporal_mismatch_detected_in_evaluator():
    """Detects when claim specifies an event date that differs from publication dates."""
    claim = "The Chernobyl disaster occurred in 1986."
    items = [
        EvidenceInput(
            evidence_id="ev-temp-1",
            exact_excerpt="A recent 2024 analysis reviewed nuclear safety standards across European facilities.",
            source_url="https://world-nuclear.org/safety-2024",
            domain="world-nuclear.org",
            publication_date="2024-05-12",
        )
    ]
    _, _, notes = evidence_sufficiency_evaluator.evaluate(claim, items)
    assert notes is not None
    assert "1986" in notes


def test_source_credibility_weighting_impact():
    """Tests that high-credibility sources elevate evidence strength above low-credibility ones."""
    claim = "Atmospheric CO2 reached 420 ppm."
    high_source = [
        EvidenceInput(
            evidence_id="ev-h",
            exact_excerpt="NOAA Mauna Loa observatory recorded 421 ppm.",
            source_url="https://noaa.gov/co2-data",
            domain="noaa.gov",
            credibility_weight=0.95,
            relevance_score=0.90,
        )
    ]
    low_source = [
        EvidenceInput(
            evidence_id="ev-l",
            exact_excerpt="A personal blog post claims CO2 is around 420 ppm.",
            source_url="https://myblog.wordpress.com/co2",
            domain="myblog.wordpress.com",
            credibility_weight=0.20,
            relevance_score=0.50,
        )
    ]
    _, str_h, _ = evidence_sufficiency_evaluator.evaluate(claim, high_source)
    _, str_l, _ = evidence_sufficiency_evaluator.evaluate(claim, low_source)
    assert str_h > str_l


def test_malformed_llm_json_raises_unavailable_exception():
    """Confirms that non-JSON LLM responses are handled safely without corrupting verdicts."""
    provider = GeminiVerificationProvider(api_key="mock-key")

    class MockBadResponse:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "This is plain text, not valid JSON."}}]}

    import httpx
    async def mock_post(*args, **kwargs):
        return MockBadResponse()

    claim_input = ClaimVerificationInput(
        investigation_id="inv-malformed",
        claim_id="c-malformed",
        claim_text="Sample statement.",
        evidence_items=[
            EvidenceInput(
                evidence_id="ev-m",
                exact_excerpt="Sample excerpt.",
                source_url="https://example.com",
            )
        ],
    )

    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(LLMProviderUnavailableException) as exc_info:
            asyncio.run(provider.verify_claim(claim_input))
        assert exc_info.value.code == "LLM_MALFORMED_OUTPUT"


def test_live_mode_does_not_silently_fallback_to_demo(monkeypatch):
    """Confirms that in LIVE mode with a failed remote LLM, no fake verdict is fabricated."""
    svc = VerificationService(provider=GeminiVerificationProvider(api_key="invalid-live-key"))

    db = TestingSessionLocal()
    try:
        inv = InvestigationRepository.create_investigation(
            db=db,
            input_type="TEXT",
            title="Live Fallback Check",
        )
        claim = InvestigationRepository.create_claim(
            db=db,
            investigation_id=inv.id,
            claim_text="Live mode strict verification assertion.",
        )
        source = InvestigationRepository.get_or_create_source(
            db=db,
            url="https://reputable.org/article",
            title="Reputable Article",
        )
        InvestigationRepository.add_evidence(
            db=db,
            claim_id=claim.id,
            source_id=source.id,
            exact_relevant_excerpt="Some evidence excerpt.",
            relationship="SUPPORTING",
        )

        results = asyncio.run(svc.verify_investigation(db=db, investigation_id=inv.id))
        # Zero fake results fabricated on remote provider error
        assert len(results) == 0
        db.refresh(claim)
        assert claim.status == "failed"
        db.refresh(inv)
        assert inv.status == "failed"
    finally:
        db.close()

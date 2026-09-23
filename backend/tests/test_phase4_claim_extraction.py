import io
import os
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.models import (
    AgentEventModel,
    ClaimModel,
    ClaimTaskModel,
    EvidenceModel,
    InputModel,
    InvestigationModel,
    TimelineEventModel,
    VerificationResultModel,
)
from backend.app.database.session import SessionLocal
from backend.app.main import app
from backend.app.schemas.claim import ClaimType, SourcePreference
from backend.app.services.llm.local_nlp import LocalNLPClaimExtractor
from backend.app.services.llm.openai_provider import OpenAILLMProvider

client = TestClient(app)


# ==============================================================================
# Helpers
# ==============================================================================

def create_ocr_image(text: str) -> bytes:
    img = Image.new("RGB", (650, 180), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((25, 60), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ==============================================================================
# 1. LOCAL NLP EXTRACTOR & DECOMPOSER TESTS
# ==============================================================================

@pytest.mark.anyio
async def test_local_nlp_compound_who_announcement_decomposition():
    """
    Decomposes:
    'The WHO announced in Geneva on May 5th, 2023 that COVID-19 is no longer a global health emergency.'
    into atomic claims: core declaration, date, and location.
    """
    extractor = LocalNLPClaimExtractor()
    compound_text = "The WHO announced in Geneva on May 5th, 2023 that COVID-19 is no longer a global health emergency."
    candidates = await extractor.extract_and_decompose_claims(compound_text, investigation_id="inv-test-who")

    assert len(candidates) >= 3

    claim_texts = [c.claim_text for c in candidates]
    types = [c.claim_type for c in candidates]

    # Verify atomic claims
    assert any("COVID-19 is no longer a global health emergency" in ct for ct in claim_texts)
    assert any("May 5th, 2023" in ct for ct in claim_texts)
    assert any("Geneva" in ct for ct in claim_texts)

    # Verify classification
    assert ClaimType.DATE in types
    assert ClaimType.LOCATION in types


@pytest.mark.anyio
async def test_local_nlp_coordinated_clause_decomposition():
    """
    Decomposes:
    'Inflation dropped by 3.2% in the UK during Q3 2023, while unemployment reached 4.1%.'
    into 2 distinct atomic statistical/economic claims.
    """
    extractor = LocalNLPClaimExtractor()
    text = "Inflation dropped by 3.2% in the UK during Q3 2023, while unemployment reached 4.1%."
    candidates = await extractor.extract_and_decompose_claims(text, investigation_id="inv-test-coord")

    assert len(candidates) == 2

    c1, c2 = candidates[0], candidates[1]
    assert "3.2%" in c1.claim_text or "3.2%" in c2.claim_text
    assert "4.1%" in c1.claim_text or "4.1%" in c2.claim_text

    # Both are statistical or economic
    assert c1.claim_type in (ClaimType.STATISTIC, ClaimType.ECONOMIC)
    assert c2.claim_type in (ClaimType.STATISTIC, ClaimType.ECONOMIC)


@pytest.mark.anyio
async def test_local_nlp_noise_and_opinion_filtering():
    """
    Ensures greetings, questions, subjective opinions, and boilerplate CTAs
    are filtered out and not extracted as claims.
    """
    extractor = LocalNLPClaimExtractor()
    noise_text = (
        "Hello everyone! "
        "What do you think about the latest election results? "
        "In my opinion this movie was the absolute worst. "
        "Click here to subscribe to our newsletter! "
        "NASA discovered water ice on the Moon in 2020."
    )
    candidates = await extractor.extract_and_decompose_claims(noise_text, investigation_id="inv-test-noise")

    # Only the verifiable NASA claim should be extracted
    assert len(candidates) == 1
    assert "NASA" in candidates[0].claim_text
    assert "water ice" in candidates[0].claim_text
    assert candidates[0].claim_type in (ClaimType.SCIENTIFIC, ClaimType.ORGANIZATION)


@pytest.mark.anyio
async def test_local_nlp_verification_task_generation():
    """
    Verifies that generated tasks include specific questions, search queries,
    and appropriate source preferences.
    """
    extractor = LocalNLPClaimExtractor()
    text = "The Federal Reserve raised interest rates by 25 basis points in July 2023."
    candidates = await extractor.extract_and_decompose_claims(text, investigation_id="inv-test-task")

    assert len(candidates) >= 1
    claim = candidates[0]
    assert len(claim.verification_tasks) >= 1

    task = claim.verification_tasks[0]
    assert task.task_description.startswith("Is it factually accurate that") or "?" in task.task_description
    assert "Federal Reserve" in task.search_query or "rates" in task.search_query
    assert task.task_status == "pending"
    assert any(pref in task.source_preferences for pref in (SourcePreference.OFFICIAL, SourcePreference.GOVERNMENT, SourcePreference.REPUTABLE_NEWS))


# ==============================================================================
# 2. INGESTION PIPELINE INTEGRATION TESTS (TEXT, IMAGE, URL, AUDIO)
# ==============================================================================

def test_verify_text_triggers_claim_extraction():
    """POST /api/v1/verify/text runs claim extraction and populates metadata counts."""
    text = "Drinking 3 liters of water daily cures type 2 diabetes according to new claims."
    res = client.post("/api/v1/verify/text", json={"text": text})
    assert res.status_code == 200
    data = res.json()

    assert data["input_type"] == "TEXT"
    assert data["status"] == "received"
    assert data["metadata"]["claims_count"] >= 1
    assert data["metadata"]["tasks_count"] >= 1
    assert data["metadata"]["claim_extraction_status"] == "tasks_created"

    inv_id = data["investigation_id"]

    # Verify DB persistence
    db = SessionLocal()
    try:
        claims = db.scalars(select(ClaimModel).where(ClaimModel.investigation_id == inv_id)).all()
        assert len(claims) >= 1
        claim = claims[0]
        assert "diabetes" in claim.claim_text.lower() or "water" in claim.claim_text.lower()
        assert claim.status == "tasks_created"
        assert len(claim.tasks) >= 1

        # Verify investigation status updated
        inv = db.get(InvestigationModel, inv_id)
        assert inv.status == "tasks_created"
    finally:
        db.close()


def test_verify_image_ocr_triggers_claim_extraction():
    """POST /api/v1/verify/image runs OCR, then extracts claims and creates tasks."""
    img_text = "NASA discovered ice on Mars in 2008."
    img_bytes = create_ocr_image(img_text)

    res = client.post(
        "/api/v1/verify/image",
        files={"file": ("mars_ice.png", io.BytesIO(img_bytes), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["input_type"] == "IMAGE"
    assert data["metadata"]["claims_count"] >= 1
    assert data["metadata"]["tasks_count"] >= 1

    inv_id = data["investigation_id"]

    db = SessionLocal()
    try:
        claims = db.scalars(select(ClaimModel).where(ClaimModel.investigation_id == inv_id)).all()
        assert len(claims) >= 1
        assert any("NASA" in c.claim_text or "Mars" in c.claim_text for c in claims)
    finally:
        db.close()


def test_verify_url_triggers_claim_extraction():
    """POST /api/v1/verify/url extracts web article and triggers claim extraction."""
    # Using example.com
    res = client.post("/api/v1/verify/url", json={"url": "https://example.com"})
    assert res.status_code == 200
    data = res.json()

    assert data["input_type"] == "URL"
    assert "claims_count" in data["metadata"]
    assert "tasks_count" in data["metadata"]


def test_verify_audio_triggers_claim_extraction():
    """POST /api/v1/verify/audio transcribes audio and extracts claims from transcript."""
    # Synthesize clean wav speech
    tmp_wav = "/tmp/phase4_audio_test.wav"
    os.system('say "Water freezes at zero degrees Celsius." -o ' + tmp_wav + ' --data-format=LEI16@16000')
    if not os.path.exists(tmp_wav):
        pytest.skip("Audio synthesis not available on system.")

    try:
        with open(tmp_wav, "rb") as f:
            audio_bytes = f.read()

        res = client.post(
            "/api/v1/verify/audio",
            files={"file": ("freeze.wav", io.BytesIO(audio_bytes), "audio/wav")},
        )
        assert res.status_code == 200
        data = res.json()

        assert data["input_type"] == "AUDIO"
        assert data["metadata"]["claims_count"] >= 1
        assert data["metadata"]["tasks_count"] >= 1

        db = SessionLocal()
        try:
            claims = db.scalars(select(ClaimModel).where(ClaimModel.investigation_id == data["investigation_id"])).all()
            assert len(claims) >= 1
            assert any("water" in c.claim_text.lower() or "freezes" in c.claim_text.lower() for c in claims)
        finally:
            db.close()
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)


# ==============================================================================
# 3. INVESTIGATION & CLAIM API ENDPOINTS
# ==============================================================================

def test_post_investigations_creates_claims_and_tasks():
    """POST /api/v1/investigations with content returns 201 and claims_count."""
    statement = "The James Webb Space Telescope detected carbon dioxide on exoplanet WASP-39 b in August 2022."
    res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": statement, "mode": "LIVE"},
    )
    assert res.status_code == 201
    data = res.json()

    assert data["status"] == "tasks_created"
    assert data["claims_count"] >= 1
    assert data["modality"] == "TEXT"
    assert data["mode"] == "LIVE"


def test_get_investigation_detail():
    """GET /api/v1/investigations/{id} returns real metadata and claims_count."""
    # First create investigation
    create_res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Global sea levels rose by 10 centimeters since 1993."},
    )
    inv_id = create_res.json()["investigation_id"]

    res = client.get(f"/api/v1/investigations/{inv_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["status"] == "tasks_created"
    assert data["claims_count"] >= 1


def test_get_investigation_status_stage():
    """GET /api/v1/investigations/{id}/status returns stage and progress percent."""
    create_res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "The European Central Bank raised interest rates to 4.0%."},
    )
    inv_id = create_res.json()["investigation_id"]

    res = client.get(f"/api/v1/investigations/{inv_id}/status")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["status"] == "tasks_created"
    assert data["current_stage"] == "TASKS_CREATED"
    assert data["progress_percent"] == 40


def test_get_investigation_claims_list():
    """GET /api/v1/investigations/{id}/claims returns atomic claims and tasks."""
    create_res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Apple announced the Vision Pro headset in Cupertino on June 5, 2023."},
    )
    inv_id = create_res.json()["investigation_id"]

    res = client.get(f"/api/v1/investigations/{inv_id}/claims")
    assert res.status_code == 200
    data = res.json()

    assert data["investigation_id"] == inv_id
    assert data["total"] >= 1
    assert len(data["claims"]) == data["total"]

    for claim in data["claims"]:
        assert "claim_text" in claim
        assert "claim_type" in claim
        assert "tasks" in claim
        assert len(claim["tasks"]) >= 1
        for task in claim["tasks"]:
            assert "task_description" in task
            assert "search_query" in task
            assert task["task_status"] == "pending"


def test_get_single_claim_by_id():
    """GET /api/v1/claims/{claim_id} returns claim detail and tasks."""
    create_res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "The Amazon rainforest produces 20% of the world's oxygen."},
    )
    inv_id = create_res.json()["investigation_id"]

    claims_res = client.get(f"/api/v1/investigations/{inv_id}/claims")
    first_claim = claims_res.json()["claims"][0]
    claim_id = first_claim["id"]

    res = client.get(f"/api/v1/claims/{claim_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["id"] == claim_id
    assert data["investigation_id"] == inv_id
    assert data["claim_text"] == first_claim["claim_text"]
    assert len(data["tasks"]) >= 1


# ==============================================================================
# 4. DATABASE INTEGRITY & OBSERVABILITY
# ==============================================================================

def test_database_timeline_and_agent_events_recorded():
    """Verifies that timeline events and agent events are recorded during claim extraction."""
    create_res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Mount Everest reaches an elevation of 8,848.86 meters."},
    )
    inv_id = create_res.json()["investigation_id"]

    db = SessionLocal()
    try:
        # Timeline events
        timeline_events = db.scalars(
            select(TimelineEventModel).where(TimelineEventModel.investigation_id == inv_id)
        ).all()
        assert len(timeline_events) >= 1
        event_types = [te.event_type for te in timeline_events]
        assert "claims_extracted" in event_types

        # Agent events
        agent_events = db.scalars(
            select(AgentEventModel).where(AgentEventModel.investigation_id == inv_id)
        ).all()
        assert len(agent_events) >= 1
        assert agent_events[0].stage == "CLAIM_EXTRACTION"
        assert agent_events[0].metadata_json.get("claims_count", 0) >= 1
    finally:
        db.close()


def test_investigation_data_isolation():
    """Ensures claims from investigation A never bleed into investigation B."""
    res_a = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Claim A: Jupiter has 95 known moons."},
    )
    inv_a = res_a.json()["investigation_id"]

    res_b = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Claim B: Saturn has 146 known moons."},
    )
    inv_b = res_b.json()["investigation_id"]

    claims_a = client.get(f"/api/v1/investigations/{inv_a}/claims").json()["claims"]
    claims_b = client.get(f"/api/v1/investigations/{inv_b}/claims").json()["claims"]

    a_ids = {c["id"] for c in claims_a}
    b_ids = {c["id"] for c in claims_b}

    assert a_ids.isdisjoint(b_ids)
    assert not any("Saturn" in c["claim_text"] for c in claims_a)
    assert not any("Jupiter" in c["claim_text"] for c in claims_b)


# ==============================================================================
# 5. ERROR HANDLING & SECURITY CONSTRAINTS
# ==============================================================================

def test_missing_investigation_returns_404():
    """GET /api/v1/investigations/{invalid_id} returns 404."""
    res = client.get("/api/v1/investigations/nonexistent-inv-uuid")
    assert res.status_code == 404
    data = res.json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_missing_claim_returns_404():
    """GET /api/v1/claims/{invalid_id} returns 404."""
    res = client.get("/api/v1/claims/nonexistent-claim-uuid")
    assert res.status_code == 404
    data = res.json()
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.anyio
async def test_openai_provider_unavailable_when_no_api_key():
    """
    OpenAILLMProvider raises LLMProviderUnavailableException (HTTP 503)
    when api_key is missing, avoiding silent fallback to fake demo data.
    """
    provider = OpenAILLMProvider(api_key="")
    with pytest.raises(Exception) as exc_info:
        await provider.extract_and_decompose_claims("Some factual statement.", investigation_id="inv-err")
    assert exc_info.value.code == "LLM_PROVIDER_UNAVAILABLE"
    assert exc_info.value.status_code == 503


def test_future_evidence_endpoint_remains_501():
    """Confirms Phase 5 evidence endpoint remains 501 Service Not Ready in Phase 4."""
    create_res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Some test claim."},
    )
    inv_id = create_res.json()["investigation_id"]

    res = client.get(f"/api/v1/investigations/{inv_id}/evidence")
    assert res.status_code == 501
    assert res.json()["status"] == "service_not_ready"


def test_zero_fake_verdicts_or_evidence_persisted():
    """Strict Phase 4 check: claims and tasks are created, but NO evidence or verdicts fabricated."""
    res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Albert Einstein published the general theory of relativity in 1915."},
    )
    inv_id = res.json()["investigation_id"]

    db = SessionLocal()
    try:
        claims = db.scalars(select(ClaimModel).where(ClaimModel.investigation_id == inv_id)).all()
        tasks = db.scalars(select(ClaimTaskModel).join(ClaimModel).where(ClaimModel.investigation_id == inv_id)).all()
        evidence = db.scalars(select(EvidenceModel)).all()
        verdicts = db.scalars(select(VerificationResultModel)).all()

        assert len(claims) >= 1
        assert len(tasks) >= 1
        # ZERO fake evidence or verdicts
        assert len(evidence) == 0
        assert len(verdicts) == 0
    finally:
        db.close()


def test_empty_or_whitespace_input_handling():
    """Confirms empty text or whitespace handles gracefully with 0 claims."""
    res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "   \n\t   "},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["claims_count"] == 0


def test_taxonomy_classification_coverage():
    """Confirms taxonomy classification covers Political, Economic, Scientific, Statistic, Quote."""
    statements = (
        'Prime Minister declared new sanctions on foreign assets. '
        'The GDP contracted by 1.8% during the second quarter. '
        'Researchers synthesized a novel enzyme at 37 degrees Celsius. '
        'Spokesperson stated: "The agreement was officially signed today."'
    )
    res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": statements},
    )
    assert res.status_code == 201
    inv_id = res.json()["investigation_id"]

    claims_res = client.get(f"/api/v1/investigations/{inv_id}/claims")
    claims = claims_res.json()["claims"]
    assert len(claims) >= 3

    types = {c["claim_type"] for c in claims}
    assert bool(types & {"POLITICAL", "ECONOMIC", "SCIENTIFIC", "STATISTIC", "QUOTE"})


def test_investigation_depth_and_mode_preservation():
    """Confirms custom depth, mode, and preferences are preserved on creation."""
    res = client.post(
        "/api/v1/investigations",
        json={
            "modality": "TEXT",
            "content": "Water boils at 100 degrees Celsius at sea level.",
            "depth": "deep",
            "mode": "DEMO",
            "evidence_preference": "official",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["mode"] == "DEMO"
    assert data["status"] == "tasks_created"

    db = SessionLocal()
    try:
        inv = db.get(InvestigationModel, data["investigation_id"])
        assert inv.verification_depth == "deep"
        assert inv.evidence_preference == "official"
        assert inv.input_mode == "DEMO"
    finally:
        db.close()


def test_multi_claim_order_indices_sequential():
    """Confirms order_index is sequentially assigned (0, 1, 2...)."""
    multi = (
        "Claim 1: The speed of light is approximately 300,000 km per second. "
        "Claim 2: Sound travels at 343 meters per second in air. "
        "Claim 3: Absolute zero is minus 273.15 degrees Celsius."
    )
    res = client.post("/api/v1/investigations", json={"modality": "TEXT", "content": multi})
    inv_id = res.json()["investigation_id"]

    claims_res = client.get(f"/api/v1/investigations/{inv_id}/claims")
    claims = claims_res.json()["claims"]
    assert len(claims) >= 3
    order_indices = [c["order_index"] for c in claims]
    assert order_indices == list(range(len(claims)))


def test_future_timeline_and_copilot_remain_501():
    """Confirms Phase 6 timeline and Phase 7 copilot remain 501 in Phase 4."""
    res_tl = client.get("/api/v1/investigations/any-inv/timeline")
    assert res_tl.status_code == 501
    assert res_tl.json()["status"] == "service_not_ready"

    res_cp = client.post("/api/v1/investigations/any-inv/copilot")
    assert res_cp.status_code == 501
    assert res_cp.json()["status"] == "service_not_ready"


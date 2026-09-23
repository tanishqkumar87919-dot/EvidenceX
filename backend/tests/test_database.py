import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.models import (
    AgentEventModel,
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
    UserModel,
    UserSettingModel,
    VerificationResultModel,
)
from backend.app.database.repository import repo, compute_content_hash


@pytest.fixture
def db_session():
    """Provides a fresh isolated in-memory database with foreign keys enforced."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# 1. Database connection
def test_01_database_connection(db_session):
    result = db_session.execute(text("SELECT 1;")).scalar()
    assert result == 1


# 2. Migration success / schema integrity
def test_02_migration_schema_integrity(db_session):
    expected_tables = {
        "users",
        "investigations",
        "inputs",
        "claims",
        "claim_tasks",
        "sources",
        "evidence",
        "claim_evidence",
        "verification_results",
        "timeline_events",
        "agent_events",
        "copilot_messages",
        "user_settings",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"


# 3. Investigation creation
def test_03_investigation_creation(db_session):
    inv = repo.create_investigation(
        db=db_session,
        input_type="TEXT",
        title="Investigation of Vaccine Claims",
    )
    assert inv.id is not None
    assert len(inv.id) == 36
    assert inv.input_mode == "LIVE"  # LIVE must be default
    assert inv.status == "queued"
    assert inv.verification_depth == "standard"
    assert inv.evidence_preference == "balanced"
    assert inv.created_at is not None


# 4. Input creation
def test_04_input_creation(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    inp = repo.create_input(
        db=db_session,
        investigation_id=inv.id,
        input_type="TEXT",
        original_text="Solar storms cause auroras on Earth.",
        metadata_dict={"source_ui": "verification_center"},
    )
    assert inp.id is not None
    assert inp.investigation_id == inv.id
    assert inp.input_type == "TEXT"
    assert inp.content_hash is not None
    assert inp.metadata_json.get("source_ui") == "verification_center"


# 5. TEXT input
def test_05_text_input(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    text_content = "Global sea levels rose by 3.6 mm per year between 2006 and 2015."
    inp = repo.create_input(
        db=db_session,
        investigation_id=inv.id,
        input_type="TEXT",
        original_text=text_content,
    )
    assert inp.original_text == text_content
    expected_hash = compute_content_hash(text_content)
    assert inp.content_hash == expected_hash


# 6. IMAGE input
def test_06_image_input(db_session):
    inv = repo.create_investigation(db=db_session, input_type="IMAGE")
    inp = repo.create_input(
        db=db_session,
        investigation_id=inv.id,
        input_type="IMAGE",
        image_storage_ref="supabase-storage://uploads/screenshots/inv_999/snap.png",
        content_hash="hash-image-12345",
    )
    assert inp.input_type == "IMAGE"
    assert inp.image_storage_reference == "supabase-storage://uploads/screenshots/inv_999/snap.png"


# 7. URL input
def test_07_url_input(db_session):
    inv = repo.create_investigation(db=db_session, input_type="URL")
    test_url = "https://www.reuters.com/world/science/space-telescope-deep-field"
    inp = repo.create_input(
        db=db_session,
        investigation_id=inv.id,
        input_type="URL",
        url=test_url,
    )
    assert inp.input_type == "URL"
    assert inp.url == test_url


# 8. AUDIO input
def test_08_audio_input(db_session):
    inv = repo.create_investigation(db=db_session, input_type="AUDIO")
    inp = repo.create_input(
        db=db_session,
        investigation_id=inv.id,
        input_type="AUDIO",
        audio_storage_ref="supabase-storage://audio/recordings/press_conf.wav",
        audio_filename="press_conf.wav",
        audio_mime_type="audio/wav",
        audio_duration=128.5,
    )
    assert inp.input_type == "AUDIO"
    assert inp.audio_filename == "press_conf.wav"
    assert inp.audio_mime_type == "audio/wav"
    assert float(inp.audio_duration) == 128.5


# 9. Audio transcript initially empty/PENDING
def test_09_audio_transcript_initially_empty_and_pending(db_session):
    inv = repo.create_investigation(db=db_session, input_type="AUDIO")
    inp = repo.create_input(
        db=db_session,
        investigation_id=inv.id,
        input_type="AUDIO",
        audio_filename="speech.mp3",
    )
    # Strictly check Phase 2 requirements:
    assert inp.audio_transcript is None, "Audio transcript MUST be NULL in Phase 2!"
    assert inp.audio_transcription_confidence is None, "Audio confidence MUST be NULL in Phase 2!"
    assert inp.audio_transcription_status == "PENDING"


# 10. Claim relationship
def test_10_claim_relationship(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    claim = repo.create_claim(
        db=db_session,
        investigation_id=inv.id,
        claim_text="The James Webb Telescope detected carbon-bearing molecules on K2-18 b.",
        claim_type="astrophysics",
        order_index=1,
    )
    assert claim.investigation_id == inv.id
    assert claim.investigation.id == inv.id
    assert len(inv.claims) == 1
    assert inv.claims[0].claim_text == claim.claim_text


# 11. Claim task relationship
def test_11_claim_task_relationship(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    claim = repo.create_claim(db=db_session, investigation_id=inv.id, claim_text="Sample Claim")
    task = repo.create_claim_task(
        db=db_session,
        claim_id=claim.id,
        task_description="Search NASA peer-reviewed statements on K2-18 b",
        search_query="NASA K2-18 b carbon molecules paper",
    )
    assert task.claim_id == claim.id
    assert task.claim.id == claim.id
    assert task.task_status == "pending"
    assert len(claim.tasks) == 1


# 12. Source relationship
def test_12_source_relationship(db_session):
    source1 = repo.get_or_create_source(
        db=db_session,
        url="https://nasa.gov/news/k2-18b-discovery",
        title="NASA Webb Finds Carbon Compounds on Habitable Zone Exoplanet",
        publisher="NASA",
        domain="nasa.gov",
    )
    assert source1.id is not None

    # Get-or-create should reuse identical URL
    source2 = repo.get_or_create_source(
        db=db_session,
        url="https://nasa.gov/news/k2-18b-discovery",
    )
    assert source1.id == source2.id


# 13. Evidence relationship
def test_13_evidence_relationship(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    claim = repo.create_claim(db=db_session, investigation_id=inv.id, claim_text="Exoplanet claim")
    source = repo.get_or_create_source(db=db_session, url="https://nature.com/articles/exoplanet-study")

    ev_supporting = repo.add_evidence(
        db=db_session,
        claim_id=claim.id,
        source_id=source.id,
        exact_relevant_excerpt="Methane and carbon dioxide were identified at high statistical significance.",
        relationship="SUPPORTING",
        relevance=0.95,
    )
    assert ev_supporting.relationship_type == "SUPPORTING"
    assert ev_supporting.source_id == source.id
    assert ev_supporting.claim_id == claim.id

    # Evidence relationship with CONTRADICTING
    ev_contradicting = repo.add_evidence(
        db=db_session,
        claim_id=claim.id,
        source_id=source.id,
        exact_relevant_excerpt="Alternative stellar activity models explain the absorption signal.",
        relationship="CONTRADICTING",
        relevance=0.88,
    )
    assert ev_contradicting.relationship_type == "CONTRADICTING"


# 14. Verification result relationship
def test_14_verification_result_relationship(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    res = repo.create_verification_result(
        db=db_session,
        investigation_id=inv.id,
        verdict="SUPPORTED",
        explanation="Multiple independent peer-reviewed spectral analyses confirm the claim.",
        confidence=0.92,
        supporting_count=4,
        contradicting_count=0,
        inconclusive_count=1,
    )
    assert res.investigation_id == inv.id
    assert res.verdict == "SUPPORTED"
    assert res.supporting_count == 4


# 15. Timeline relationship
def test_15_timeline_relationship(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    event = repo.add_timeline_event(
        db=db_session,
        investigation_id=inv.id,
        event_type="claim_origin",
        description="Initial pre-print uploaded to arXiv.",
        event_date=datetime(2023, 9, 11, 10, 0, tzinfo=timezone.utc),
    )
    assert event.investigation_id == inv.id
    assert len(inv.timeline_events) == 1


# 16. Agent event relationship
def test_16_agent_event_relationship(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    ae = repo.add_agent_event(
        db=db_session,
        investigation_id=inv.id,
        event_type="claim_extraction_completed",
        stage="decomposition",
        message="Extracted 3 atomic claims from submitted statement.",
        metadata_dict={"claims_count": 3},
    )
    assert ae.investigation_id == inv.id
    assert ae.metadata_json["claims_count"] == 3


# 17. Copilot message relationship
def test_17_copilot_message_relationship(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    msg = repo.add_copilot_message(
        db=db_session,
        investigation_id=inv.id,
        role="assistant",
        message="The primary corroborating study was published in the Astrophysical Journal Letters.",
        citations=[{"source_id": "src-1", "title": "ApJL 2023 Study"}],
    )
    assert msg.investigation_id == inv.id
    assert len(msg.citations) == 1


# 18. User settings
def test_18_user_settings(db_session):
    user = UserModel(email=f"user_{uuid.uuid4().hex[:8]}@evidencex.io", full_name="Lead Analyst")
    db_session.add(user)
    db_session.commit()

    settings = UserSettingModel(
        user_id=user.id,
        language="hi",
        theme="dark",
        verification_depth="deep",
        evidence_preference="official",
    )
    db_session.add(settings)
    db_session.commit()

    assert user.settings.theme == "dark"
    assert user.settings.language == "hi"


# 19. Investigation deletion (cascade)
def test_19_investigation_deletion_cascade(db_session):
    inv = repo.create_investigation(db=db_session, input_type="TEXT")
    inv_id = inv.id

    # Create child records
    inp = repo.create_input(db=db_session, investigation_id=inv_id, input_type="TEXT", original_text="Claim text")
    claim = repo.create_claim(db=db_session, investigation_id=inv_id, claim_text="Claim")
    task = repo.create_claim_task(db=db_session, claim_id=claim.id, task_description="Task")
    source = repo.get_or_create_source(db=db_session, url=f"https://source-{uuid.uuid4().hex[:6]}.com")
    ev = repo.add_evidence(db=db_session, claim_id=claim.id, source_id=source.id, exact_relevant_excerpt="Excerpt")
    res = repo.create_verification_result(db=db_session, investigation_id=inv_id, verdict="SUPPORTED")
    tl = repo.add_timeline_event(db=db_session, investigation_id=inv_id, event_type="event", description="timeline")
    ag = repo.add_agent_event(db=db_session, investigation_id=inv_id, event_type="agent", message="event")
    cp = repo.add_copilot_message(db=db_session, investigation_id=inv_id, role="user", message="query")

    # Capture all primary keys prior to cascade deletion
    inp_id = inp.id
    claim_id = claim.id
    task_id = task.id
    ev_id = ev.id
    res_id = res.id
    tl_id = tl.id
    ag_id = ag.id
    cp_id = cp.id

    # Delete investigation
    deleted = repo.delete_investigation(db=db_session, investigation_id=inv_id)
    assert deleted is True

    # Verify all child records were cascade-deleted
    assert db_session.get(InvestigationModel, inv_id) is None
    assert db_session.get(InputModel, inp_id) is None
    assert db_session.get(ClaimModel, claim_id) is None
    assert db_session.get(ClaimTaskModel, task_id) is None
    assert db_session.get(EvidenceModel, ev_id) is None
    assert db_session.get(VerificationResultModel, res_id) is None
    assert db_session.get(TimelineEventModel, tl_id) is None
    assert db_session.get(AgentEventModel, ag_id) is None
    assert db_session.get(CopilotMessageModel, cp_id) is None


# 20. Foreign-key integrity / source reuse
def test_20_foreign_key_integrity_and_source_reuse(db_session):
    inv1 = repo.create_investigation(db=db_session, input_type="TEXT")
    claim1 = repo.create_claim(db=db_session, investigation_id=inv1.id, claim_text="First Claim")

    # Shared source referenced by Investigation 1
    shared_url = f"https://shared-authority-{uuid.uuid4().hex[:6]}.gov/report"
    source = repo.get_or_create_source(db=db_session, url=shared_url)
    ev1 = repo.add_evidence(db=db_session, claim_id=claim1.id, source_id=source.id, exact_relevant_excerpt="Excerpt 1")

    # When inv1 is deleted, the shared source MUST remain intact!
    repo.delete_investigation(db=db_session, investigation_id=inv1.id)
    assert db_session.get(SourceModel, source.id) is not None, "Shared source was erroneously deleted!"


# 21. Investigation isolation
def test_21_investigation_isolation(db_session):
    # Investigation A (LIVE)
    inv_a = repo.create_investigation(db=db_session, input_type="TEXT", title="Investigation A")
    claim_a = repo.create_claim(db=db_session, investigation_id=inv_a.id, claim_text="Private Claim A")
    inp_a = repo.create_input(db=db_session, investigation_id=inv_a.id, input_type="TEXT", original_text="Text A")

    # Investigation B (LIVE)
    inv_b = repo.create_investigation(db=db_session, input_type="TEXT", title="Investigation B")
    claim_b = repo.create_claim(db=db_session, investigation_id=inv_b.id, claim_text="Private Claim B")
    inp_b = repo.create_input(db=db_session, investigation_id=inv_b.id, input_type="TEXT", original_text="Text B")

    # Scoped queries for Investigation A MUST NOT return records from Investigation B
    claims_for_a = repo.get_claims_for_investigation(db=db_session, investigation_id=inv_a.id)
    inputs_for_a = repo.get_inputs_for_investigation(db=db_session, investigation_id=inv_a.id)

    claim_ids_a = {c.id for c in claims_for_a}
    input_ids_a = {i.id for i in inputs_for_a}

    assert claim_a.id in claim_ids_a
    assert claim_b.id not in claim_ids_a, "Data leakage! Claim from Investigation B found in A!"
    assert inp_a.id in input_ids_a
    assert inp_b.id not in input_ids_a, "Data leakage! Input from Investigation B found in A!"


# 22. LIVE vs DEMO separation
def test_22_live_vs_demo_separation(db_session):
    live_inv = repo.create_investigation(
        db=db_session,
        input_type="TEXT",
        input_mode="LIVE",
        title="Real-World Live Submission",
    )
    demo_inv = repo.create_investigation(
        db=db_session,
        input_type="TEXT",
        input_mode="DEMO",
        title="Pre-scripted Demo Case",
    )

    assert live_inv.input_mode == "LIVE"
    assert demo_inv.input_mode == "DEMO"

    # Query strictly for LIVE investigations
    live_stmt = select(InvestigationModel).where(InvestigationModel.input_mode == "LIVE")
    live_investigations = list(db_session.scalars(live_stmt).all())
    live_ids = {inv.id for inv in live_investigations}

    assert live_inv.id in live_ids
    assert demo_inv.id not in live_ids, "DEMO investigation leaked into LIVE query results!"

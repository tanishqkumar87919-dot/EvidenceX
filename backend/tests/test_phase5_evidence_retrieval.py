import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.database.models import (
    Base,
    ClaimEvidenceModel,
    ClaimModel,
    ClaimTaskModel,
    EvidenceChunkModel,
    EvidenceModel,
    InvestigationModel,
    SourceModel,
)
from backend.app.database.repository import InvestigationRepository
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.services.embeddings.base import EmbeddingProvider
from backend.app.services.embeddings.factory import get_embedding_provider
from backend.app.services.embeddings.local_provider import LocalHashingEmbeddingProvider
from backend.app.services.rag.chunker import EvidenceChunker
from backend.app.services.rag.credibility import SourceCredibilityEvaluator
from backend.app.services.rag.extractor import DocumentExtractor
from backend.app.services.rag.fetcher import FetchResult, SourceFetcher
from backend.app.services.rag.ranking import HybridEvidenceRanker, RankedEvidenceCandidate
from backend.app.services.rag.retrieval import RetrievedChunk, VectorRetrievalEngine
from backend.app.services.rag.service import EvidenceRetrievalService
from backend.app.services.search.base import SearchResult, WebSearchProvider
from backend.app.services.search.duckduckgo_provider import DuckDuckGoSearchProvider
from backend.app.services.search.factory import get_search_provider, get_web_search_provider
from backend.app.services.search.mock_provider import MockSearchProvider

from sqlalchemy.pool import StaticPool

client = TestClient(app)

# Isolated in-memory SQLite database for deterministic Phase 5 unit and integration tests
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


@pytest.fixture(autouse=True)
def scoped_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)



# ==============================================================================
# 1. Web Search Provider Abstraction & Providers
# ==============================================================================

def test_mock_search_provider():
    provider = MockSearchProvider()
    assert isinstance(provider, WebSearchProvider)
    assert provider.provider_name == "mock"

    import asyncio
    results = asyncio.run(provider.search("renewable energy solar power", max_results=3))
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].url.startswith("https://")
    assert results[0].title != ""
    assert results[0].snippet != ""


def test_search_provider_factory():
    mock_p = get_web_search_provider("mock")
    assert isinstance(mock_p, MockSearchProvider)

    ddg_p = get_web_search_provider("duckduckgo")
    assert isinstance(ddg_p, DuckDuckGoSearchProvider)

    alias_p = get_search_provider("mock")
    assert isinstance(alias_p, MockSearchProvider)


# ==============================================================================
# 2. Source Fetcher
# ==============================================================================

def test_source_fetcher_invalid_protocol():
    import asyncio
    fetcher = SourceFetcher()
    res = asyncio.run(fetcher.fetch_page("ftp://invalid.com/file.txt"))
    assert not res.success
    assert res.status_code == 400
    assert "Invalid URL" in (res.error or "")


def test_source_fetcher_empty_url():
    import asyncio
    fetcher = SourceFetcher()
    res = asyncio.run(fetcher.fetch_page(""))
    assert not res.success
    assert res.status_code == 400


# ==============================================================================
# 3. Document Extractor & HTML Cleaning
# ==============================================================================

def test_document_extractor_html_cleaning():
    extractor = DocumentExtractor()
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>NASA Webb Detects Carbon Dioxide on Exoplanet</title>
        <meta name="author" content="Jane Astronomer">
        <meta name="og:site_name" content="NASA Goddard">
        <link rel="canonical" href="https://nasa.gov/webb-exoplanet">
    </head>
    <body>
        <nav><a href="/">Home</a><a href="/news">News</a></nav>
        <script>console.log("tracking script");</script>
        <style>body { background: white; }</style>
        <article>
            <h1>NASA Webb Detects Carbon Dioxide on Exoplanet</h1>
            <h2>Major Discovery</h2>
            <p>NASA's James Webb Space Telescope has provided the first clear evidence for carbon dioxide in the atmosphere of an exoplanet, WASP-39 b.</p>
            <p>This discovery confirms that Webb is able to detect key atmospheric molecules in exoplanets at high precision.</p>
        </article>
        <footer>Copyright 2023 NASA. All rights reserved.</footer>
    </body>
    </html>
    """
    doc = extractor.extract(sample_html, "https://nasa.gov/webb-exoplanet")
    assert "NASA Webb Detects Carbon Dioxide on Exoplanet" in doc.title
    assert "Jane Astronomer" == doc.author
    assert "NASA Goddard" == doc.publisher
    assert doc.canonical_url == "https://nasa.gov/webb-exoplanet"
    assert "Major Discovery" in doc.headings
    # Scripts, styles, nav, footer must NOT appear in body text
    assert "console.log" not in doc.body_text
    assert "background: white" not in doc.body_text
    assert "carbon dioxide in the atmosphere" in doc.body_text
    assert doc.character_count > 50
    assert doc.word_count > 10


# ==============================================================================
# 4. Source Credibility Evaluator
# ==============================================================================

def test_source_credibility_categories():
    evaluator = SourceCredibilityEvaluator()

    # Government / Official
    gov = evaluator.assess_source("https://www.nasa.gov/missions/webb/article-123")
    assert gov.source_type == "OFFICIAL"
    assert gov.credibility_weight >= 0.90

    # Academic
    acad = evaluator.assess_source("https://arxiv.org/abs/2208.11692")
    assert acad.source_type == "ACADEMIC"
    assert acad.credibility_weight >= 0.90

    # Fact Check
    fc = evaluator.assess_source("https://www.snopes.com/fact-check/climate-data")
    assert fc.source_type == "FACT_CHECK"
    assert fc.credibility_weight >= 0.85

    # Reputable News
    news = evaluator.assess_source("https://www.reuters.com/science/space-telescope-discovery")
    assert news.source_type == "REPUTABLE_NEWS"
    assert news.credibility_weight >= 0.80

    # Other
    other = evaluator.assess_source("https://random-unverified-blog.xyz/post")
    assert other.source_type == "OTHER"
    assert other.credibility_weight <= 0.70


# ==============================================================================
# 5. Evidence Chunker & Overlap
# ==============================================================================

def test_evidence_chunker_boundaries_and_overlap():
    extractor = DocumentExtractor()
    long_body = "\n\n".join([
        f"Paragraph {i}: The James Webb Space Telescope observed WASP-39b with its Near-Infrared Spectrograph revealing a distinct carbon dioxide bump."
        for i in range(12)
    ])
    html = f"<html><body><article><h1>JWST Findings</h1>{long_body}</article></body></html>"
    doc = extractor.extract(html, "https://example.com/findings")

    chunker = EvidenceChunker(chunk_size=300, chunk_overlap=50)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.character_count > 0
        assert chunk.token_count > 0
        assert chunk.url == "https://example.com/findings"


# ==============================================================================
# 6. Embedding Providers & Dimensionality
# ==============================================================================

def test_local_hashing_embedding_provider():
    import asyncio
    provider = LocalHashingEmbeddingProvider(dimension=768)
    assert provider.dimension == 768
    assert provider.provider_name == "local_hash"

    vec1 = asyncio.run(provider.embed_text("James Webb Space Telescope detected carbon dioxide"))
    assert len(vec1) == 768
    assert all(isinstance(x, float) for x in vec1)

    # Determinism: same input produces identical vector
    vec2 = asyncio.run(provider.embed_text("James Webb Space Telescope detected carbon dioxide"))
    assert vec1 == vec2

    # Different inputs produce different vectors
    vec3 = asyncio.run(provider.embed_text("Completely unrelated statement about culinary techniques"))
    assert vec1 != vec3

    # Batch embedding
    batch = asyncio.run(provider.embed_texts(["Claim A", "Claim B"]))
    assert len(batch) == 2
    assert len(batch[0]) == 768
    assert len(batch[1]) == 768


# ==============================================================================
# 7. Vector Similarity & Cosine Calculation
# ==============================================================================

def test_vector_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    sim = VectorRetrievalEngine._cosine_similarity(v1, v2)
    assert pytest.approx(sim, 0.0001) == 1.0

    v3 = [0.0, 1.0, 0.0]
    sim_ortho = VectorRetrievalEngine._cosine_similarity(v1, v3)
    assert pytest.approx(sim_ortho, 0.0001) == 0.0

    # Empty vectors
    assert VectorRetrievalEngine._cosine_similarity([], []) == 0.0


# ==============================================================================
# 8. Hybrid Ranker & Stance Classification
# ==============================================================================

def test_hybrid_evidence_ranker():
    ranker = HybridEvidenceRanker()
    claim = "The James Webb Space Telescope detected carbon dioxide in exoplanet atmosphere."

    chunks = [
        RetrievedChunk(
            chunk_id="chunk-1",
            investigation_id="inv-1",
            claim_id="claim-1",
            source_id="src-1",
            chunk_index=0,
            content="NASA confirmed that the James Webb Space Telescope detected carbon dioxide in the atmosphere of WASP-39 b.",
            heading="Exoplanet Atmosphere",
            similarity_score=0.88,
            source_url="https://nasa.gov/article-1",
            source_title="NASA JWST Exoplanet Discovery",
            publisher="NASA",
            source_type="OFFICIAL",
        ),
        RetrievedChunk(
            chunk_id="chunk-2",
            investigation_id="inv-1",
            claim_id="claim-1",
            source_id="src-2",
            chunk_index=0,
            content="Astronomers denied rumors and disproven claims that aliens were detected on Mars.",
            heading="Mars Reports",
            similarity_score=0.45,
            source_url="https://reuters.com/mars-debunk",
            source_title="Mars Debunk",
            publisher="Reuters",
            source_type="REPUTABLE_NEWS",
        ),
    ]

    ranked = ranker.rank_and_deduplicate(claim, chunks, top_k=2)
    assert len(ranked) == 2
    top = ranked[0]
    assert top.source_url == "https://nasa.gov/article-1"
    assert top.relationship == "SUPPORTING"
    assert top.relevance_score >= 0.70
    assert "carbon dioxide" in top.exact_excerpt.lower()

    contradicting = ranked[1]
    assert contradicting.relationship == "CONTRADICTING"


# ==============================================================================
# 9. Database Repository & Persistence Tests
# ==============================================================================

def test_repository_source_and_evidence_persistence():
    db = TestingSessionLocal()
    try:
        inv = InvestigationRepository.create_investigation(
            db=db,
            input_type="TEXT",
            title="JWST Investigation",
        )
        claim = InvestigationRepository.create_claim(
            db=db,
            investigation_id=inv.id,
            claim_text="JWST detected carbon dioxide on WASP-39b.",
            claim_type="FACTUAL",
        )
        source = InvestigationRepository.get_or_create_source(
            db=db,
            url="https://nasa.gov/jwst-wasp39b",
            title="NASA Webb Discovery",
            publisher="NASA",
            domain="nasa.gov",
            source_type="OFFICIAL",
        )
        assert source.id is not None
        assert source.domain == "nasa.gov"

        chunk = InvestigationRepository.create_evidence_chunk(
            db=db,
            investigation_id=inv.id,
            source_id=source.id,
            claim_id=claim.id,
            content="Webb detected carbon dioxide on WASP-39b.",
            chunk_index=0,
            embedding=[0.1] * 768,
            embedding_model="test-embedding",
        )
        assert chunk.id is not None
        assert chunk.chunk_index == 0

        ev = InvestigationRepository.add_evidence(
            db=db,
            claim_id=claim.id,
            source_id=source.id,
            exact_relevant_excerpt="Webb detected carbon dioxide on WASP-39b.",
            relationship="SUPPORTING",
            relevance=0.92,
            source_assessment={"source_type": "OFFICIAL", "domain": "nasa.gov"},
        )
        assert ev.id is not None
        assert ev.relationship_type == "SUPPORTING"

        # Verify query methods
        evidence_list = InvestigationRepository.get_evidence_for_investigation(db, inv.id)
        assert len(evidence_list) == 1
        assert evidence_list[0].id == ev.id

        claim_ev_list = InvestigationRepository.get_evidence_for_claim(db, claim.id)
        assert len(claim_ev_list) == 1
        assert claim_ev_list[0].id == ev.id

        sources = InvestigationRepository.get_sources_for_investigation(db, inv.id)
        assert len(sources) >= 1
        assert sources[0].url == "https://nasa.gov/jwst-wasp39b"

        ev_by_id = InvestigationRepository.get_evidence_by_id(db, ev.id)
        assert ev_by_id is not None
        assert ev_by_id.exact_relevant_excerpt == "Webb detected carbon dioxide on WASP-39b."
    finally:
        db.close()


# ==============================================================================
# 10. EvidenceRetrievalService End-to-End Orchestration (with Mock Provider)
# ==============================================================================

def test_evidence_retrieval_service_orchestration():
    import asyncio
    db = TestingSessionLocal()
    try:
        inv = InvestigationRepository.create_investigation(
            db=db,
            input_type="TEXT",
            title="Orchestration Test",
        )
        claim = InvestigationRepository.create_claim(
            db=db,
            investigation_id=inv.id,
            claim_text="Solar photovoltaic cells convert sunlight into electric current.",
            claim_type="SCIENTIFIC",
        )
        task = InvestigationRepository.create_claim_task(
            db=db,
            claim_id=claim.id,
            task_description="Search scientific sources on solar photovoltaic mechanism",
            search_query="solar photovoltaic cells convert sunlight electricity",
        )

        mock_search = MockSearchProvider()
        local_embed = LocalHashingEmbeddingProvider(dimension=768)

        svc = EvidenceRetrievalService(
            search_provider=mock_search,
            embedding_provider=local_embed,
        )

        evidence = asyncio.run(svc.retrieve_for_investigation(db=db, investigation_id=inv.id))

        assert len(evidence) > 0
        db.refresh(inv)
        # Investigation transitioned to ready_for_verification
        assert inv.status == "ready_for_verification"

        # Claim transitioned to evidence_retrieved
        db.refresh(claim)
        assert claim.status == "evidence_retrieved"

        # Task transitioned to completed
        db.refresh(task)
        assert task.task_status == "completed"
        assert task.completion_time is not None

        # Chunks were persisted
        chunks = InvestigationRepository.get_evidence_chunks_for_investigation(db, inv.id)
        assert len(chunks) > 0
    finally:
        db.close()


# ==============================================================================
# 11. API Endpoints Tests
# ==============================================================================

def test_api_investigation_evidence_endpoints():
    db = TestingSessionLocal()
    try:
        inv = InvestigationRepository.create_investigation(
            db=db,
            input_type="TEXT",
            title="API Evidence Test",
        )
        claim = InvestigationRepository.create_claim(
            db=db,
            investigation_id=inv.id,
            claim_text="Photosynthesis produces glucose and oxygen.",
        )
        source = InvestigationRepository.get_or_create_source(
            db=db,
            url="https://academic.edu/photosynthesis-study",
            title="Photosynthesis Study",
            publisher="Academic Press",
            domain="academic.edu",
            source_type="ACADEMIC",
        )
        ev = InvestigationRepository.add_evidence(
            db=db,
            claim_id=claim.id,
            source_id=source.id,
            exact_relevant_excerpt="Photosynthesis produces glucose and oxygen from carbon dioxide and water.",
            relationship="SUPPORTING",
            relevance=0.95,
        )
        ev_id = str(ev.id)
        inv_id = str(inv.id)
        claim_id = str(claim.id)
    finally:
        db.close()

    # 1. GET /api/v1/investigations/{inv_id}/evidence
    res1 = client.get(f"/api/v1/investigations/{inv_id}/evidence")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["investigation_id"] == inv_id
    assert data1["total"] == 1
    assert data1["evidence"][0]["evidence_id"] == ev_id
    assert data1["evidence"][0]["stance"] == "supporting"
    assert data1["evidence"][0]["source_url"] == "https://academic.edu/photosynthesis-study"

    # 2. GET /api/v1/investigations/{inv_id}/sources
    res2 = client.get(f"/api/v1/investigations/{inv_id}/sources")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["investigation_id"] == inv_id
    assert data2["total"] >= 1
    assert data2["sources"][0]["url"] == "https://academic.edu/photosynthesis-study"

    # 3. GET /api/v1/claims/{claim_id}/evidence
    res3 = client.get(f"/api/v1/claims/{claim_id}/evidence")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["total"] == 1
    assert data3["evidence"][0]["evidence_id"] == ev_id

    # 4. GET /api/v1/evidence/{evidence_id}
    res4 = client.get(f"/api/v1/evidence/{ev_id}")
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["evidence_id"] == ev_id
    assert "Photosynthesis" in data4["snippet"]

    # 5. Non-existent evidence returns 404
    res5 = client.get("/api/v1/evidence/non-existent-uuid-999")
    assert res5.status_code == 404


def test_system_status_reports_phase_5_ready():
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    data = res.json()
    assert data["subsystems"]["evidence_retrieval"] == "phase_5_ready"


def test_zero_secret_exposure_in_phase_5():
    res = client.get("/api/v1/system/status")
    content = res.text.lower()
    for secret_keyword in ["password", "secret", "service_role", "apikey", "postgresql://"]:
        assert secret_keyword not in content

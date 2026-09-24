from fastapi.testclient import TestClient
from backend.app.database.models import ClaimModel, EvidenceModel, InvestigationModel, SourceModel
from backend.app.database.session import SessionLocal
from backend.app.main import app

client = TestClient(app)


def test_api_v1_routes_exist():
    """Verify that all required v1 endpoints are registered and routed."""
    db = SessionLocal()
    try:
        if not db.get(InvestigationModel, "test-inv-123"):
            db.add(InvestigationModel(id="test-inv-123", input_type="TEXT", input_mode="LIVE", status="received"))
            db.commit()
        if not db.get(ClaimModel, "test-claim-456"):
            db.add(ClaimModel(id="test-claim-456", investigation_id="test-inv-123", claim_text="Test routing claim"))
            db.commit()
        if not db.get(SourceModel, "test-src-123"):
            db.add(SourceModel(id="test-src-123", url="https://example.com/routing-test", title="Test Routing Source"))
            db.commit()
        if not db.get(EvidenceModel, "test-ev-789"):
            db.add(EvidenceModel(id="test-ev-789", claim_id="test-claim-456", source_id="test-src-123", exact_relevant_excerpt="Test routing evidence excerpt", relationship_type="SUPPORTING"))
            db.commit()
    finally:
        db.close()
    routes = [
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/system/status"),
        ("POST", "/api/v1/verify/text"),
        ("POST", "/api/v1/verify/url"),
        ("POST", "/api/v1/verify/image"),
        ("POST", "/api/v1/verify/audio"),
        ("POST", "/api/v1/investigations"),
        ("GET", "/api/v1/investigations/test-inv-123"),
        ("GET", "/api/v1/investigations/test-inv-123/status"),
        ("GET", "/api/v1/investigations/test-inv-123/claims"),
        ("GET", "/api/v1/investigations/test-inv-123/evidence"),
        ("GET", "/api/v1/investigations/test-inv-123/timeline"),
        ("POST", "/api/v1/investigations/test-inv-123/copilot"),
        ("GET", "/api/v1/claims/test-claim-456"),
        ("GET", "/api/v1/evidence/test-ev-789"),
        ("GET", "/api/v1/timeline/test-inv-123"),
        ("GET", "/api/v1/analytics/overview"),
        ("POST", "/api/v1/copilot"),
        ("GET", "/api/v1/settings"),
        ("PUT", "/api/v1/settings"),
    ]

    for method, path in routes:
        # None of these routes should return 404 Not Found (route exists)
        if method == "GET":
            response = client.get(path)
        else:
            response = client.post(path, json={})
        assert response.status_code != 404, f"Route {method} {path} was not found (404)"

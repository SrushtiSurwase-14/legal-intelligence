"""Day 6 - the HTTP contract."""
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from tests.conftest import make_settings


@pytest.fixture(scope="module")
def client(service):
    return TestClient(create_app(service=service), raise_server_exceptions=False)


Q = {"question": "What weekly rest is an employee entitled to under the Freedonia Shops and Establishments Act?"}


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "ok" and b["system"]["corpus_docs"] == 7 and b["system"]["corpus_fingerprint"]


def test_research_response_contract(client):
    r = client.post("/research", json=Q)
    assert r.status_code == 200
    b = r.json()
    for k in ["trace_id", "status", "request", "question_analysis", "candidate_sources", "evidence", "version_notes",
              "conflicts", "limitations", "confidence", "steps", "system"]:
        assert k in b
    assert b["request"]["question"] == Q["question"] and b["trace_id"] and b["system"]["app_version"]
    assert "analysis" not in b


def test_analyze_response_contract(client):
    r = client.post("/analyze", json={**Q, "jurisdiction": "Freedonia", "as_of_date": "2024-01-01"})
    assert r.status_code == 200
    b = r.json()
    assert b["analysis"]["requires_professional_review"] in (True, False)
    assert b["answer_summary"] and b["evidence"] and b["analysis"]["relevant_sources"]


def test_trace_ids_are_unique(client):
    a, b = client.post("/research", json=Q).json(), client.post("/research", json=Q).json()
    assert a["trace_id"] != b["trace_id"]


@pytest.mark.parametrize("payload", [{}, {"question": 5}, {"question": "x" * 2001},
                                     {"question": "ok question here", "as_of_date": "not-a-date"},
                                     {"question": "ok question here", "top_k": 99}])
def test_schema_validation_returns_422(client, payload):
    assert client.post("/analyze", json=payload).status_code == 422


def test_semantic_malformed_question_is_200_with_status(client):
    r = client.post("/analyze", json={"question": "???"})
    assert r.status_code == 200 and r.json()["status"] == "malformed_question"


def test_no_evidence_is_200_with_limitations_not_an_error(client):
    r = client.post("/analyze", json={"question": "Describe quantum entanglement experiments."})
    b = r.json()
    assert r.status_code == 200 and b["status"] == "insufficient_evidence" and b["evidence"] == []
    assert b["limitations"][0]["code"] == "NO_SOURCE_FOUND"


def test_unhandled_error_returns_500_with_trace_id(service, monkeypatch):
    c = TestClient(create_app(service=service), raise_server_exceptions=False)
    monkeypatch.setattr(service, "research", lambda req: (_ for _ in ()).throw(RuntimeError("x")))
    r = c.post("/research", json=Q)
    assert r.status_code == 500 and r.json()["trace_id"] and r.json()["status"] == "error"
    assert "RuntimeError" not in r.text                      # no internals leaked


def test_degraded_health_when_corpus_has_bad_metadata(tmp_corpus):
    (tmp_corpus / "broken.meta.json").write_text("{not json", encoding="utf-8")
    c = TestClient(create_app(settings=make_settings(corpus_dir=tmp_corpus)))
    r = c.get("/health")
    assert r.status_code == 503 and r.json()["status"] == "degraded" and r.json()["problems"]


def test_service_not_ready_when_startup_fails(tmp_path):
    c = TestClient(create_app(settings=make_settings(corpus_dir=tmp_path / "does-not-exist")))
    assert c.get("/health").status_code == 503
    assert c.post("/research", json=Q).status_code == 503


def test_trace_file_is_written(tmp_path):
    from app.service import LegalIntelligenceService
    svc = LegalIntelligenceService(make_settings(trace_dir=tmp_path))
    c = TestClient(create_app(service=svc))
    tid = c.post("/analyze", json=Q).json()["trace_id"]
    assert tid in (tmp_path / "traces.jsonl").read_text()

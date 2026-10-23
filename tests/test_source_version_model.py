"""Day 3: source & version information is captured, validated and preserved end to end."""
import json
from datetime import date

import pytest

from app.config import ROOT
from app.ingestion import Corpus
from app.models import ResearchRequest, Source
from tests.conftest import write_doc

REQUIRED = ["jurisdiction", "issuing_authority", "document_type", "publication_date", "effective_date",
            "amendment_status", "source_url", "version", "retrieval_date"]


def test_every_sample_document_has_complete_metadata():
    c = Corpus(ROOT / "data" / "corpus")
    assert not c.load_errors and not c.warnings
    for s in c.sources.values():
        for f in REQUIRED:
            assert hasattr(s, f)
        assert s.source_url and s.version and s.retrieval_date
        if s.role.value == "primary":
            assert s.effective_date is not None


def test_invalid_metadata_is_recorded_not_swallowed(tmp_corpus):
    (tmp_corpus / "bad.meta.json").write_text(json.dumps({"doc_id": "bad"}), encoding="utf-8")
    c = Corpus(tmp_corpus)
    assert any("bad.meta.json" in e for e in c.load_errors)
    assert "d1" in c.sources  # the good document still loads


def test_unknown_metadata_field_is_rejected():
    with pytest.raises(Exception):
        Source.model_validate({"doc_id": "x", "typo_field": 1})


def test_inconsistent_amendment_status_is_warned(tmp_corpus):
    write_doc(tmp_corpus, "amender", "Section 1. Change. Hours are now 7 hours.",
              relations=[{"type": "amends", "target": "d1", "affected_sections": ["1"]}])
    c = Corpus(tmp_corpus)  # d1.amendment_status is 'original' although amended
    assert any("amendment_status" in w for w in c.warnings)


def test_version_metadata_survives_into_api_response(service):
    r = service.research(ResearchRequest(
        question="What is the daily working hour limit under the Freedonia Shops and Establishments Act?"))
    ids = {c.source.doc_id: c.source for c in r.candidate_sources}
    act = ids["act_2010"]
    assert act.version == "2010-original" and act.effective_date == date(2010, 7, 1)
    assert act.source_url.startswith("synthetic://") and act.retrieval_date == date(2026, 10, 22)
    assert act.amendment_status == "amended" and act.issuing_authority and act.jurisdiction == "Freedonia"
    for e in r.evidence:
        assert e.version and e.source_url and e.jurisdiction

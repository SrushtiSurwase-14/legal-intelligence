"""Day 5 - FAILURE & SAFETY. One automated test per required situation (plus dependency failures).

Principle under test:  NO EVIDENCE -> NO FABRICATED CONCLUSION -> EXPLAIN LIMITATION -> ASK FOR MISSING INFO -> ESCALATE
"""
import shutil
from datetime import date

import pytest

from app.config import ROOT
from app.fallbacks import POLICY
from app.models import FailureCode as F, Label, ResearchRequest, Status
from tests.conftest import make_settings, write_doc
from app.service import LegalIntelligenceService

CONCLUSION_LABELS = {Label.VERIFIED, Label.SOURCE_DERIVED, Label.INTERPRETATION}


def codes(r):
    return {l.code for l in r.limitations}


def no_conclusion(r):
    assert r.evidence == []
    assert r.confidence == "none"
    assert not any(s.label in CONCLUSION_LABELS for s in r.analysis.analysis)
    assert r.analysis.applicable_provisions == []
    assert r.analysis.requires_professional_review or r.status == Status.MALFORMED_QUESTION or r.status == Status.ERROR


# 1 ---------------------------------------------------------------------------
def test_1_no_source_found(service):
    r = service.analyze(ResearchRequest(question="Describe quantum entanglement experiments."))
    assert r.status == Status.INSUFFICIENT_EVIDENCE and F.NO_SOURCE_FOUND in codes(r)
    no_conclusion(r)
    assert r.analysis.recommended_next_step


# 2 ---------------------------------------------------------------------------
def test_2a_source_unavailable_all(fresh_service):
    svc = fresh_service(simulate_failure="source")
    r = svc.analyze(ResearchRequest(question="What weekly rest is an employee entitled to in Freedonia?"))
    assert r.status == Status.INSUFFICIENT_EVIDENCE and F.SOURCE_UNAVAILABLE in codes(r)
    assert any(l.severity == "blocking" for l in r.limitations)
    no_conclusion(r)


def test_2b_source_deleted_after_indexing_is_detected(tmp_path):
    shutil.copytree(ROOT / "data" / "corpus", tmp_path / "c")
    svc = LegalIntelligenceService(make_settings(corpus_dir=tmp_path / "c"))
    (tmp_path / "c" / "holidays_2020.txt").unlink()
    r = svc.analyze(ResearchRequest(question="How many paid public holidays are employees entitled to in Freedonia?"))
    assert F.SOURCE_UNAVAILABLE in codes(r)
    assert "holidays_2020" not in {e.doc_id for e in r.evidence}     # lost source is not used or invented
    assert any(c.availability == "unavailable" for c in r.candidate_sources)
    assert r.status in (Status.PARTIAL, Status.INSUFFICIENT_EVIDENCE)


def test_2c_source_modified_after_indexing_is_detected(tmp_path):
    shutil.copytree(ROOT / "data" / "corpus", tmp_path / "c")
    svc = LegalIntelligenceService(make_settings(corpus_dir=tmp_path / "c"))
    p = tmp_path / "c" / "act_2010.txt"
    p.write_text(p.read_text().replace("9 hours", "7 hours"))
    r = svc.analyze(ResearchRequest(question="What weekly rest is an employee entitled to under the Freedonia Shops and Establishments Act?"))
    assert F.SOURCE_UNAVAILABLE in codes(r)
    assert not any("7 hours" in e.quote for e in r.evidence)


# 3 ---------------------------------------------------------------------------
def test_3_conflicting_sources(service):
    r = service.analyze(ResearchRequest(question="Do I need to register my shop with 7 employees in Northern Province?"))
    assert F.CONFLICTING_SOURCES in codes(r) and r.conflicts
    assert r.analysis.requires_professional_review and r.confidence == "low"
    assert any(s.label == Label.CONFLICTING for s in r.analysis.analysis)


def test_3b_amendment_is_not_reported_as_conflict(service):
    r = service.research(ResearchRequest(question="What is the daily working hours limit under the Freedonia Shops and Establishments Act?"))
    assert r.conflicts == [] and F.CONFLICTING_SOURCES not in codes(r)


# 4 ---------------------------------------------------------------------------
def test_4_poor_retrieval(service):
    r = service.analyze(ResearchRequest(question="What is the tax rate on cryptocurrency gains in Freedonia?"))
    assert r.status == Status.INSUFFICIENT_EVIDENCE and F.POOR_RETRIEVAL in codes(r)
    no_conclusion(r)
    assert all(not c.selected for c in r.candidate_sources)       # weak matches listed, never used


# 5 ---------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["", "???", "hours", "!!! ### $$$ %%%"])
def test_5_malformed_question(service, q):
    r = service.analyze(ResearchRequest(question=q))
    assert r.status == Status.MALFORMED_QUESTION and F.MALFORMED_QUESTION in codes(r)
    assert [s.status for s in r.steps][1:] == ["skipped"] * 5     # nothing downstream ran
    no_conclusion(r)


# 6 ---------------------------------------------------------------------------
def test_6_missing_facts(service):
    r = service.analyze(ResearchRequest(question="Do I need to register my shop in Freedonia?"))
    assert F.MISSING_FACTS in codes(r) and r.status == Status.PARTIAL
    assert any("employee_count" in m for m in r.analysis.facts_missing)
    assert any(s.label == Label.MISSING for s in r.analysis.analysis)
    assert not any(s.label == Label.INTERPRETATION for s in r.analysis.analysis)   # rule NOT applied to unknown facts


def test_6b_facts_supplied_via_api_remove_the_gap(service):
    r = service.analyze(ResearchRequest(question="Do I need to register my shop in Freedonia?", facts={"employee_count": 12}))
    assert F.MISSING_FACTS not in codes(r)
    assert any(s.label == Label.INTERPRETATION and "meets" in s.text for s in r.analysis.analysis)
    assert r.analysis.requires_professional_review                 # interpretation always escalates


# 7 ---------------------------------------------------------------------------
def test_7_model_failure_falls_back_to_evidence_only(fresh_service):
    svc = fresh_service(simulate_failure="llm")
    r = svc.analyze(ResearchRequest(question="What weekly rest is an employee entitled to under the Freedonia Shops and Establishments Act?"))
    assert F.MODEL_FAILURE in codes(r)
    assert r.analysis.generated_by == "extractive_fallback"
    assert r.evidence and any(s.label == Label.VERIFIED for s in r.analysis.analysis)
    assert r.status == Status.PARTIAL


# 8 ---------------------------------------------------------------------------
def test_8_unsupported_legal_conclusion(service):
    r = service.analyze(ResearchRequest(question="Will I win my case if my employer made me work 10 hours a day in Freedonia?"))
    assert F.UNSUPPORTED_CONCLUSION in codes(r)
    assert r.analysis.requires_professional_review
    assert any(s.label == Label.UNCERTAIN and "no such conclusion" in s.text for s in r.analysis.analysis)
    assert r.confidence in ("low", "none")


# 9 ---------------------------------------------------------------------------
def test_9_outdated_secondary_only(service):
    r = service.analyze(ResearchRequest(question="Is a tea break required for employees in Freedonia?"))
    assert {F.SECONDARY_ONLY, F.OUTDATED_SOURCE} <= codes(r)
    assert r.confidence == "low" and r.analysis.requires_professional_review
    assert r.analysis.what_is_clear == []                          # nothing is presented as "clear" from commentary


def test_9b_superseded_without_replacement_is_a_warning(tmp_corpus):
    write_doc(tmp_corpus, "old", "Section 1. Holidays. Employees get 3 holidays in a year.",
              amendment_status="superseded", title="Old Holidays Order")
    svc = LegalIntelligenceService(make_settings(corpus_dir=tmp_corpus))
    r = svc.analyze(ResearchRequest(question="How many holidays do employees get in a year?"))
    assert any(l.code == F.OUTDATED_SOURCE and l.severity == "warning" for l in r.limitations)
    assert r.evidence[0].provision_status == "superseded_replacement_unknown"


# 10 --------------------------------------------------------------------------
def test_10a_ambiguous_jurisdiction_missing(service):
    r = service.analyze(ResearchRequest(question="Do I need to register my business with 7 employees?"))
    assert F.AMBIGUOUS_JURISDICTION in codes(r)
    assert any("jurisdiction" in m for m in r.missing_facts)
    assert {"act_2010", "province_rules_2021"} <= {e.doc_id for e in r.evidence}   # all plausible shown


def test_10b_unknown_jurisdiction_blocks(service):
    r = service.analyze(ResearchRequest(question="What weekly rest is an employee entitled to?", jurisdiction="Narnia"))
    assert r.status == Status.INSUFFICIENT_EVIDENCE and F.AMBIGUOUS_JURISDICTION in codes(r)
    no_conclusion(r)


# dependency failure (Test E) -------------------------------------------------
def test_E_retriever_failure_is_visible_and_no_answer_is_invented(fresh_service):
    svc = fresh_service(simulate_failure="retriever")
    r = svc.analyze(ResearchRequest(question="What weekly rest is an employee entitled to in Freedonia?"))
    assert r.status == Status.ERROR and F.RETRIEVAL_FAILURE in codes(r)
    failed = [s for s in r.steps if s.status == "failed"]
    assert failed and failed[0].name == "source_discovery"
    no_conclusion(r)


def test_unexpected_exception_becomes_internal_error(fresh_service, monkeypatch):
    svc = fresh_service()
    monkeypatch.setattr(svc.pipeline, "_run", lambda st: (_ for _ in ()).throw(RuntimeError("boom")))
    r = svc.analyze(ResearchRequest(question="What weekly rest is an employee entitled to in Freedonia?"))
    assert r.status == Status.ERROR and F.INTERNAL_ERROR in codes(r)
    assert r.trace_id


# policy table ------------------------------------------------------------------
def test_every_failure_code_has_a_policy():
    assert set(POLICY) == set(F)


def test_failure_matrix_doc_matches_implementation():
    import subprocess, sys
    out = subprocess.run([sys.executable, "scripts/make_failure_matrix.py", "--check"], cwd=ROOT,
                         capture_output=True, text=True, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stdout + out.stderr

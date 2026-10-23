"""Day 7 style scenarios A-D plus behaviours of the controlled research path."""
from datetime import date

from app.models import FailureCode as F, ResearchRequest, Status


def codes(resp):
    return {l.code for l in resp.limitations}


def test_A_straightforward_question(service):
    r = service.analyze(ResearchRequest(
        question="Under the Freedonia Shops and Establishments Act, what is the maximum number of hours an "
                 "employee can be required to work in a day?", as_of_date=date(2020, 6, 1)))
    assert r.status == Status.ANSWERED and r.confidence in ("high", "medium")
    assert any("8 hours" in e.quote for e in r.evidence)
    assert all(e.verified for e in r.evidence)


def test_B_multiple_sources_conflict_not_resolved(service):
    r = service.analyze(ResearchRequest(question="Do I need to register my shop with 7 employees in Northern Province?"))
    assert r.status == Status.PARTIAL and F.CONFLICTING_SOURCES in codes(r)
    docs = {e.doc_id for e in r.evidence}
    assert {"act_2010", "province_rules_2021"} <= docs
    assert len(r.conflicts) == 1 and "NOT RESOLVED" in r.conflicts[0].resolution
    assert r.analysis.requires_professional_review and r.confidence == "low"
    texts = " ".join(s.text for s in r.analysis.analysis)
    assert "does not meet" in texts and "meets" in texts   # both thresholds shown, neither chosen


def test_C_versions_exposed_in_analysis(service):
    r = service.analyze(ResearchRequest(
        question="How many paid public holidays are employees entitled to in Freedonia?", as_of_date=date(2021, 3, 1)))
    assert {"holidays_2012", "holidays_2020"} <= {e.doc_id for e in r.evidence}
    assert any(p.status == "superseded" for p in r.analysis.applicable_provisions)
    assert any(p.status == "in_force" and "12" in p.quote for p in r.analysis.applicable_provisions)


def test_D_unanswerable_gives_no_conclusion(service):
    r = service.analyze(ResearchRequest(question="What is the tax rate on cryptocurrency gains in Freedonia?"))
    assert r.status == Status.INSUFFICIENT_EVIDENCE and r.confidence == "none"
    assert r.evidence == [] and F.POOR_RETRIEVAL in codes(r)
    assert "No evidence-backed" in r.answer_summary
    assert not any(s.label.value in ("VERIFIED", "SOURCE_DERIVED", "INTERPRETATION") for s in r.analysis.analysis)


def test_primary_preferred_secondary_context_only(service):
    r = service.research(ResearchRequest(question="How many hours can an employee work per day in Freedonia?"))
    blog = next(c for c in r.candidate_sources if c.source.doc_id == "blog_2018")
    assert not blog.selected and "context only" in blog.selection_reason
    assert all(e.role.value == "primary" for e in r.evidence)


def test_every_step_is_recorded(service):
    r = service.research(ResearchRequest(question="What weekly rest is an employee entitled to in Freedonia?"))
    assert [s.name for s in r.steps] == ["question_analysis", "source_discovery", "source_validation",
                                         "retrieval_selection", "version_resolution", "evidence_extraction"]
    assert all(s.status == "ok" for s in r.steps)


def test_evidence_offsets_match_source_text(service):
    r = service.research(ResearchRequest(question="What weekly rest is an employee entitled to in Freedonia?"))
    for e in r.evidence:
        assert service.corpus.read_text(e.doc_id)[e.char_start:e.char_end] == e.quote


def test_risk_provision_is_surfaced_separately(service):
    r = service.analyze(ResearchRequest(question="What weekly rest is an employee entitled to in Freedonia?"))
    assert any(e.purpose == "risk" for e in r.evidence)
    assert "5000" in r.analysis.risk_restriction


def test_jurisdiction_filter_excludes_province_for_national_question(service):
    r = service.research(ResearchRequest(question="Is registration required for an establishment?",
                                         jurisdiction="Freedonia"))
    assert "province_rules_2021" not in {e.doc_id for e in r.evidence}


def test_deterministic_output(service):
    req = ResearchRequest(question="How is overtime computed under the Freedonia Shops and Establishments Act?")
    a, b = service.analyze(req), service.analyze(req)
    strip = lambda r: r.model_dump(mode="json", exclude={"trace_id", "steps"})
    assert strip(a) == strip(b)


def test_summary_leads_with_current_text_not_superseded_text(service):
    r = service.analyze(ResearchRequest(
        question="What is the maximum number of hours an employee can be required to work in a day?",
        jurisdiction="Freedonia", as_of_date=date(2020, 6, 1)))
    assert r.answer_summary.index("8 hours") < r.answer_summary.index("9 hours")

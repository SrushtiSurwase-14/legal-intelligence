"""Day 4 structured output + hallucination guard around LLM-written narrative."""
import json

import pytest

from app.analysis import ModelOutputInvalid, parse_and_validate
from app.llm import FakeLLM
from app.models import FailureCode as F, Label, LegalAnalysis, ResearchRequest
from tests.conftest import make_settings
from app.service import LegalIntelligenceService

Q = "What weekly rest is an employee entitled to under the Freedonia Shops and Establishments Act?"
FIELDS = ["question", "facts_provided", "facts_missing", "relevant_sources", "applicable_provisions", "analysis",
          "what_is_clear", "what_is_unclear", "risk_restriction", "recommended_next_step",
          "requires_professional_review"]


def test_analysis_has_every_required_field_in_template_order(service):
    r = service.analyze(ResearchRequest(question=Q))
    assert list(LegalAnalysis.model_fields)[:len(FIELDS)] == FIELDS
    a = r.analysis
    assert a.question == Q and a.relevant_sources and a.applicable_provisions and a.analysis
    assert isinstance(a.requires_professional_review, bool) and a.confidence_basis and a.disclaimer


def test_every_statement_points_at_real_evidence(service):
    r = service.analyze(ResearchRequest(question="How many paid public holidays are employees entitled to in Freedonia?"))
    ids = {e.evidence_id for e in r.evidence}
    for s in r.analysis.analysis:
        if s.label in (Label.VERIFIED, Label.SOURCE_DERIVED, Label.INTERPRETATION):
            assert s.evidence_ids and set(s.evidence_ids) <= ids


def test_verified_quotes_really_are_in_the_source(service):
    r = service.analyze(ResearchRequest(question=Q))
    for s in r.analysis.analysis:
        if s.label == Label.VERIFIED:
            e = next(x for x in r.evidence if x.evidence_id == s.evidence_ids[0])
            assert e.quote in service.corpus.read_text(e.doc_id) and e.quote in s.text


def good_json(service):
    r = service.research(ResearchRequest(question=Q))
    eid = r.evidence[0].evidence_id
    return json.dumps({"analysis": [{"text": "The Act gives one paid rest day in every period of 7 days.",
                                     "label": "SOURCE_DERIVED", "evidence_ids": [eid]}],
                       "what_is_clear": ["One paid rest day per 7 days."], "what_is_unclear": [],
                       "recommended_next_step": "Check the official text."})


def llm_service(response):
    svc = LegalIntelligenceService(make_settings(analyzer_mode="llm"))
    svc.llm = FakeLLM(response)
    svc.analyzer.llm = svc.llm
    return svc


def test_valid_llm_output_is_accepted(service):
    svc = llm_service(good_json(service))
    r = svc.analyze(ResearchRequest(question=Q))
    assert r.analysis.generated_by == "llm" and F.MODEL_FAILURE not in {l.code for l in r.limitations}
    assert any("paid rest day" in s.text and s.label == Label.SOURCE_DERIVED for s in r.analysis.analysis)
    assert any(s.label == Label.VERIFIED for s in r.analysis.analysis)      # verified quotes always kept


@pytest.mark.parametrize("bad,why", [
    ("not json at all", "json"),
    (json.dumps({"analysis": []}), "non-empty"),
    (json.dumps({"analysis": [{"text": "x", "label": "SOURCE_DERIVED", "evidence_ids": ["E99"]}]}), "unknown evidence"),
    (json.dumps({"analysis": [{"text": "Employees get 13 rest days.", "label": "SOURCE_DERIVED", "evidence_ids": ["E1"]}]}), "numbers"),
    (json.dumps({"analysis": [{"text": "This is definitely legal.", "label": "SOURCE_DERIVED", "evidence_ids": ["E1"]}]}), "certainty"),
    (json.dumps({"analysis": [{"text": "A claim with no support.", "label": "SOURCE_DERIVED", "evidence_ids": []}]}), "no evidence ids"),
    (json.dumps({"analysis": [{"text": "x", "label": "VERIFIED", "evidence_ids": ["E1"]}]}), "not allowed"),
])
def test_invalid_llm_output_is_rejected_with_fallback(service, bad, why):
    svc = llm_service(bad)
    r = svc.analyze(ResearchRequest(question=Q))
    assert F.MODEL_FAILURE in {l.code for l in r.limitations}, why
    assert r.analysis.generated_by == "extractive_fallback"
    assert r.evidence                                       # evidence survives model failure


def test_llm_not_called_when_there_is_no_evidence(service):
    svc = llm_service("should never be used")
    r = svc.analyze(ResearchRequest(question="Describe quantum entanglement experiments."))
    assert svc.llm.calls == [] and r.evidence == []        # a model can never answer from memory


def test_fenced_json_is_accepted(service):
    svc = llm_service("```json\n" + good_json(service) + "\n```")
    assert svc.analyze(ResearchRequest(question=Q)).analysis.generated_by == "llm"

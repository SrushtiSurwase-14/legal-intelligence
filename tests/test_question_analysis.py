from datetime import date

import pytest

from app.config import ROOT
from app.jurisdiction import JurisdictionTree
from app.models import ResearchRequest
from app.question import analyze_question

TREE = JurisdictionTree.load(ROOT / "data" / "corpus" / "jurisdictions.json")
TODAY = date(2026, 10, 22)


def qa(q, **kw):
    return analyze_question(ResearchRequest(question=q, **kw), TREE, TODAY)


@pytest.mark.parametrize("q", ["", "   ", "???", "ok", "12345 6789 000", "a b"])
def test_malformed_questions_are_invalid(q):
    r = qa(q)
    assert not r.valid and r.issues


def test_too_long_question_rejected_by_schema_and_by_analyzer():
    import pydantic
    with pytest.raises(pydantic.ValidationError):          # layer 1: API schema (HTTP 422)
        ResearchRequest(question="word " * 500)
    raw = ResearchRequest.model_construct(question="word " * 500, jurisdiction=None, as_of_date=None,
                                          facts={}, top_k=None)   # layer 2: defence in depth
    assert not analyze_question(raw, TREE, TODAY).valid


def test_jurisdiction_from_text_prefers_child():
    r = qa("Do shops in Freedonia Northern Province need to register?")
    assert r.jurisdiction == "Freedonia/Northern Province" and r.jurisdiction_source == "question_text"


def test_jurisdiction_from_request_and_unknown():
    assert qa("What are the working hours rules?", jurisdiction="freedonia").jurisdiction == "Freedonia"
    assert qa("What are the working hours rules?", jurisdiction="Narnia").jurisdiction_unrecognised == "Narnia"


def test_employee_count_and_applicability_detected():
    r = qa("Does my shop with 12 employees need registration?")
    assert r.facts_provided["employee_count"] == 12 and r.is_applicability and "registration" in r.topics


def test_dates():
    assert qa("rules in 2015 for hours").as_of_year == 2015
    assert qa("rules on 2020-03-05 for hours").as_of_date == date(2020, 3, 5)
    assert qa("rules for hours today").as_of_assumed


def test_act_year_in_title_is_not_mistaken_for_as_of_date():
    r = qa("What does the Freedonia Shops and Establishments Act, 2010 say about hours?")
    assert r.as_of_year is None and r.as_of_assumed


def test_conclusion_seeking_detected():
    assert qa("Will I win my case against my employer over overtime?").seeks_legal_conclusion
    assert not qa("What is the overtime rate?").seeks_legal_conclusion

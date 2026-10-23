"""Day 3 required test: an older document and a newer one that modifies it - relationship must be exposed."""
from datetime import date

from app.models import ResearchRequest

Q = "What is the maximum daily working hours under the Freedonia Shops and Establishments Act?"


def _by_doc(resp, doc):
    return [e for e in resp.evidence if e.doc_id == doc]


def test_older_and_newer_documents_are_both_exposed(service):
    r = service.research(ResearchRequest(question=Q, as_of_date=date(2020, 6, 1)))
    assert _by_doc(r, "act_2010") and _by_doc(r, "notif_2019")      # nothing silently dropped
    rel = [n for n in r.version_notes if n.relation == "amends"]
    assert rel and rel[0].from_doc == "notif_2019" and rel[0].to_doc == "act_2010"
    assert rel[0].affected_sections == ["4"] and rel[0].effective_date == date(2019, 4, 1)


def test_after_amendment_new_text_is_in_force_old_is_marked_superseded(service):
    r = service.research(ResearchRequest(question=Q, as_of_date=date(2020, 6, 1)))
    old = next(e for e in _by_doc(r, "act_2010") if e.section_id == "4")
    new = _by_doc(r, "notif_2019")[0]
    assert old.provision_status == "superseded_by_amendment" and old.related_doc_id == "notif_2019"
    assert new.provision_status == "in_force" and "8 hours" in new.quote and "9 hours" in old.quote


def test_before_amendment_old_text_is_in_force(service):
    r = service.research(ResearchRequest(question=Q, as_of_date=date(2015, 1, 1)))
    old = next(e for e in _by_doc(r, "act_2010") if e.section_id == "4")
    new = _by_doc(r, "notif_2019")[0]
    assert old.provision_status == "in_force" and new.provision_status == "not_yet_in_force"


def test_year_only_in_amendment_year_is_flagged_uncertain(service):
    r = service.research(ResearchRequest(question=Q + " in 2019"))
    old = next(e for e in _by_doc(r, "act_2010") if e.section_id == "4")
    assert old.provision_status == "uncertain_timing"
    assert any(n.as_of_state == "ambiguous" for n in r.version_notes)


def test_year_in_question_text_is_parsed(service):
    r = service.research(ResearchRequest(question=Q + " in 2015"))
    assert r.question_analysis.as_of_year == 2015 and not r.question_analysis.as_of_assumed


def test_no_date_assumes_today_and_says_so(service):
    r = service.research(ResearchRequest(question=Q))
    qa = r.question_analysis
    assert qa.as_of_assumed and qa.as_of_date == date(2026, 10, 22) and qa.assumptions


def test_replaced_order_is_superseded_and_replacement_shown(service):
    r = service.research(ResearchRequest(question="How many paid public holidays are employees entitled to in Freedonia?"))
    old, new = _by_doc(r, "holidays_2012")[0], _by_doc(r, "holidays_2020")[0]
    assert old.provision_status == "superseded" and new.provision_status == "in_force"
    assert any(n.relation == "supersedes" for n in r.version_notes)


def test_replaced_order_before_replacement_date(service):
    r = service.research(ResearchRequest(question="How many paid public holidays are employees entitled to in Freedonia?",
                                         as_of_date=date(2015, 5, 1)))
    assert _by_doc(r, "holidays_2012")[0].provision_status == "in_force"
    assert _by_doc(r, "holidays_2020")[0].provision_status == "not_yet_in_force"


def test_secondary_commentary_is_flagged_outdated(service):
    r = service.research(ResearchRequest(question="Is a tea break required for employees in Freedonia?"))
    blog = next(c for c in r.candidate_sources if c.source.doc_id == "blog_2018")
    assert any(f.startswith("outdated") for f in blog.flags)

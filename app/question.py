"""Step 1 - question analysis: validity, jurisdiction, time frame, topics, facts, risky intent."""
from __future__ import annotations

import re
from datetime import date

from .jurisdiction import JurisdictionTree
from .models import QuestionAnalysis, ResearchRequest
from .textutil import stem, tokenize, topics_of

MAX_LEN = 2000
_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
_YEAR = re.compile(r"\b(?:in|during|as of|in the year|for the year|on)\s+((?:19|20)\d{2})\b", re.I)
_FIRST_PERSON = re.compile(r"\b(my|our|we|i|us|me)\b", re.I)
_EMP_COUNT = re.compile(r"\b(\d{1,6})\s+(?:full[- ]time\s+|part[- ]time\s+)?(?:employees|employee|workers|staff|persons|people)\b", re.I)
_CONCLUSION = re.compile(
    r"\b(will i win|will we win|win (?:my|the|our) case|am i liable|are we liable|am i guilty|"
    r"will the court|should i sue|chances of (?:winning|success)|guarantee|"
    r"can i be (?:jailed|arrested|prosecuted|sent to jail)|will i (?:go to jail|be jailed|be arrested))\b",
    re.I,
)


def analyze_question(req: ResearchRequest, tree: JurisdictionTree, today: date) -> QuestionAnalysis:
    q = (req.question or "").strip()
    qa = QuestionAnalysis(raw=req.question or "", valid=True)

    # ---- validity (malformed question)
    words = [t for t in tokenize(q) if not t.isdigit()]
    non_space = re.sub(r"\s", "", q)
    letters = sum(ch.isalpha() for ch in non_space)
    if not q:
        qa.issues.append("question is empty")
    elif len(q) > MAX_LEN:
        qa.issues.append(f"question is longer than {MAX_LEN} characters")
    elif len(words) < 3:
        qa.issues.append("question is too short to analyse (needs at least 3 words)")
    elif letters / max(len(non_space), 1) < 0.5:
        qa.issues.append("question is mostly non-text characters")
    if qa.issues:
        qa.valid = False
        return qa

    # ---- jurisdiction
    exclude: list[str] = []
    detected = tree.detect(q)
    if detected:
        exclude = [stem(t) for t in tokenize(detected[1])]
    if req.jurisdiction and req.jurisdiction.strip():
        resolved = tree.resolve(req.jurisdiction)
        if resolved:
            qa.jurisdiction, qa.jurisdiction_source = resolved, "request"
        else:
            qa.jurisdiction_unrecognised = req.jurisdiction.strip()
    elif detected:
        qa.jurisdiction, qa.jurisdiction_source = detected[0], "question_text"
    qa.exclude_terms = exclude

    # ---- time frame (as-of)
    if req.as_of_date:
        qa.as_of_date, qa.as_of_description = req.as_of_date, f"{req.as_of_date.isoformat()} (provided)"
    else:
        m = _ISO.search(q)
        y = _YEAR.search(q)
        if m:
            try:
                qa.as_of_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                qa.as_of_description = f"{qa.as_of_date.isoformat()} (from question text)"
            except ValueError:
                qa.issues.append("date in question is not a valid calendar date")
        elif y:
            qa.as_of_year = int(y.group(1))
            qa.as_of_description = f"year {qa.as_of_year} (from question text; exact date unknown)"
        if qa.as_of_date is None and qa.as_of_year is None:
            qa.as_of_date, qa.as_of_assumed = today, True
            qa.as_of_description = f"{today.isoformat()} (assumed: today / current law)"
            qa.assumptions.append("No date was given, so the question was treated as being about the law "
                                  f"currently in force on {today.isoformat()}.")

    # ---- topics, intent, facts
    qa.topics = sorted(topics_of(q))
    qa.is_applicability = bool(_FIRST_PERSON.search(q))
    qa.seeks_legal_conclusion = bool(_CONCLUSION.search(q))
    facts = {k.lower(): v for k, v in (req.facts or {}).items()}
    m = _EMP_COUNT.search(q)
    if "employee_count" not in facts and m:
        facts["employee_count"] = int(m.group(1))
    if qa.jurisdiction:
        facts["jurisdiction"] = qa.jurisdiction
    facts["as_of"] = qa.as_of_description
    qa.facts_provided = facts
    return qa

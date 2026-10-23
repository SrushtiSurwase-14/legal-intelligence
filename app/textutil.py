"""Small, dependency-free text helpers shared by ingestion, retrieval and analysis."""
from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an the and or of to in on at by for with from as is are was were be been being it its this that these
    those what which who whom whose how why when where does do did can could should would will may might must
    shall per under than then there their them they i me my we our us you your he she his her not no if any
    every each such into within about also law laws legal legally number many much maximum minimum""".split()
)

_TOKEN = re.compile(r"[a-z0-9]+")
STEM_LEN = 6


def stem(tok: str) -> str:
    """Very light stemmer: plural strip, -ing/-ed strip, truncate to 6 chars.

    Crude on purpose (register/registration/registered -> 'regist'). It is deterministic and
    easy to explain; see docs/STUDY_GUIDE.md for its limits.
    """
    if tok.isdigit():
        return tok
    if len(tok) > 4 and tok.endswith("ies"):
        tok = tok[:-3] + "y"
    elif len(tok) > 4 and tok.endswith("sses"):
        tok = tok[:-2]
    elif len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        tok = tok[:-1]
    for suf in ("ing", "ed"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            tok = tok[: -len(suf)]
            break
    return tok[:STEM_LEN]


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _is_content(tok: str) -> bool:
    if tok in STOPWORDS:
        return False
    return tok.isdigit() or len(tok) >= 2


def index_stems(text: str) -> list[str]:
    """Stems used for indexing (keeps repeats and numbers)."""
    return [stem(t) for t in tokenize(text) if _is_content(t)]


def query_terms(text: str, exclude: tuple[str, ...] | list[str] = ()) -> list[str]:
    """Distinct content stems of a query, in order. Pure numbers are dropped (they are facts, not topics)."""
    seen: list[str] = []
    ex = set(exclude)
    for t in tokenize(text):
        if t.isdigit() or not _is_content(t):
            continue
        s = stem(t)
        if s in ex or s in seen:
            continue
        seen.append(s)
    return seen


_SENT_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'\[(])")
_HEADING = re.compile(r"^Section\s+\d+[A-Za-z]?\.$")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENT_BREAK.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def pick_sentences(text: str, terms: list[str], max_n: int = 2) -> tuple[int, int] | None:
    """Return (start, end) of the best 1-2 sentences for the query terms (verbatim span of `text`)."""
    all_spans = [(s, e) for s, e in sentence_spans(text) if not _HEADING.match(text[s:e].strip())]
    # drop short heading-like sentences ("Penalties.", "Daily hours of work.") when real sentences exist
    spans = [(s, e) for s, e in all_spans if len(text[s:e].split()) > 4] or all_spans
    if not spans:
        return None
    tset = set(terms)
    scored = []
    for i, (s, e) in enumerate(spans):
        ov = len(tset & set(index_stems(text[s:e])))
        scored.append((ov, i))
    best = [i for ov, i in sorted(scored, key=lambda x: (-x[0], x[1])) if ov > 0][:max_n]
    if not best:  # no lexical overlap: fall back to the first operative sentence
        best = [0]
    best.sort()
    # merge only adjacent sentences into one verbatim span; otherwise keep the strongest one
    if len(best) == 2 and best[1] != best[0] + 1:
        top = max(best, key=lambda i: scored[i][0])
        best = [top]
    s0, e0 = spans[best[0]][0], spans[best[-1]][1]
    return s0, e0


# ---- topics and quantities (used for conflict detection and missing-fact rules) ----
_TOPIC_WORDS = {
    "registration": ["register", "registration", "registered", "registering"],
    "working_hours": ["hours", "hour", "shift", "daily", "workday"],
    "weekly_rest": ["rest", "weekly"],
    "overtime": ["overtime", "extra"],
    "penalty": ["penalty", "penalties", "fine", "fined", "punishable", "punishment", "offence", "offense",
                "contravene", "contravenes", "contravention", "prosecution", "jailed", "imprisonment",
                "arrested", "prosecuted"],
    "holidays": ["holiday", "holidays"],
}
TOPIC_STEMS = {k: {stem(w) for w in v} for k, v in _TOPIC_WORDS.items()}


def topics_of(text: str) -> set[str]:
    stems = set(index_stems(text))
    return {t for t, ws in TOPIC_STEMS.items() if stems & ws}


_QTY = re.compile(
    r"\b(\d[\d,]*)\s+(?:or more\s+)?(?:paid\s+)?(?:public\s+)?"
    r"(hours?|days?|persons?|employees?|workers?|people|units?|holidays?)\b",
    re.I,
)
_UNIT_MAP = {"hour": "hours", "day": "days", "person": "persons", "employee": "persons",
             "worker": "persons", "people": "persons", "unit": "units", "holiday": "holidays"}


def quantities(text: str) -> dict[str, set[int]]:
    """Map normalised unit -> set of integers stated with that unit, e.g. {'hours': {9}}."""
    out: dict[str, set[int]] = {}
    for m in _QTY.finditer(text):
        base = m.group(2).lower().rstrip("s")
        unit = _UNIT_MAP.get(base, base)
        out.setdefault(unit, set()).add(int(m.group(1).replace(",", "")))
    return out

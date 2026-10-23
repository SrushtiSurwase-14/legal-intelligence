"""Day 3 - legal context & version awareness.

Core rule: the system never silently picks "the newest" document. It exposes how documents relate
(amends / supersedes / clarifies / describes), whether each instrument was in effect on the as-of
date, and which provisions have been replaced.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .ingestion import Corpus
from .models import Chunk, Conflict, Source, VersionNote
from .textutil import quantities, topics_of


@dataclass(frozen=True)
class AsOf:
    date: date | None
    year: int | None
    assumed: bool = False


def effective_state(eff: date | None, asof: AsOf) -> str:
    """Was an instrument with this effective date in force on the as-of date?"""
    if eff is None:
        return "unknown"
    if asof.date is not None:
        return "effective" if eff <= asof.date else "not_yet"
    if asof.year is not None:
        if eff.year < asof.year:
            return "effective"
        if eff.year > asof.year:
            return "not_yet"
        return "ambiguous"
    return "unknown"


def provision_status(corpus: Corpus, doc: Source, section_id: str | None, asof: AsOf
                     ) -> tuple[str, str, str | None]:
    """(status, explanation, related_doc_id) for one provision of one document."""
    st = effective_state(doc.effective_date, asof)
    if st == "not_yet":
        return ("not_yet_in_force",
                f"{doc.title} took effect on {doc.effective_date}, after the as-of date "
                f"({_asof_text(asof)}); shown for version context only.", None)
    ambiguous: tuple[str, str, str | None] | None = None
    for other, rel in corpus.incoming(doc.doc_id):
        if rel.type not in ("amends", "supersedes"):
            continue
        whole_doc = rel.type == "supersedes" or not rel.affected_sections
        if not whole_doc and (section_id is None or section_id not in rel.affected_sections):
            continue
        ost = effective_state(other.effective_date, asof)
        if ost == "effective":
            kind = "superseded" if rel.type == "supersedes" else "superseded_by_amendment"
            verb = "replaced" if rel.type == "supersedes" else "amended"
            return (kind, f"This text was {verb} by '{other.title}' (effective {other.effective_date}); "
                          f"per the source metadata it is not the current text for the as-of date.", other.doc_id)
        if ost == "ambiguous":
            ambiguous = ("uncertain_timing",
                         f"'{other.title}' took effect on {other.effective_date}, in the same year as the "
                         f"as-of year; the exact date is needed to know which text applied.", other.doc_id)
    if ambiguous:
        return ambiguous
    has_replacement_doc = any(r.type == "supersedes" for _, r in corpus.incoming(doc.doc_id))
    if doc.amendment_status == "superseded" and not has_replacement_doc:
        return ("superseded_replacement_unknown",
                "Marked as superseded but no replacing document is available in the corpus.", None)
    return "in_force", "", None


def _asof_text(asof: AsOf) -> str:
    if asof.date:
        return asof.date.isoformat() + (" - assumed today" if asof.assumed else "")
    return f"year {asof.year}" if asof.year else "unknown"


_STATE_SENTENCE = {
    "effective": "It was already in effect on the as-of date, so the amended/replacing text is the one in force "
                 "(the original text is shown only for comparison).",
    "not_yet": "It was NOT yet in effect on the as-of date, so the earlier text applied at that time.",
    "ambiguous": "It took effect in the same year as the as-of year; the exact date is needed to know which "
                 "text applied.",
    "unknown": "Its effective date is unknown, so the system cannot say which text applied.",
}


def build_version_notes(corpus: Corpus, doc_ids: list[str], asof: AsOf) -> list[VersionNote]:
    """One note per relation touching any of the given documents (both directions), de-duplicated."""
    notes: dict[tuple[str, str, str], VersionNote] = {}
    for d in doc_ids:
        rels = [(corpus.sources[d], r) for r in corpus.sources[d].relations if r.target in corpus.sources]
        rels += corpus.incoming(d)
        for src, r in rels:
            key = (r.type, src.doc_id, r.target)
            if key in notes:
                continue
            tgt = corpus.sources[r.target]
            state = effective_state(src.effective_date, asof)
            secs = f" (sections: {', '.join(r.affected_sections)})" if r.affected_sections else ""
            if r.type == "describes":
                msg = (f"'{src.title}' (secondary, published {src.publication_date}) describes '{tgt.title}'. "
                       "It is commentary, not authority.")
                if _published_before_change(corpus, src, tgt):
                    msg += " It was published before a later change to that law and may be outdated."
            else:
                msg = (f"'{src.title}' (effective {src.effective_date}) {r.type} '{tgt.title}'{secs}. "
                       f"{_STATE_SENTENCE[state]}")
            notes[key] = VersionNote(relation=r.type, from_doc=src.doc_id, to_doc=tgt.doc_id,
                                     from_title=src.title, to_title=tgt.title,
                                     effective_date=src.effective_date, affected_sections=r.affected_sections,
                                     as_of_state=state, message=msg)
    return list(notes.values())


def _published_before_change(corpus: Corpus, secondary: Source, target: Source) -> bool:
    for other, rel in corpus.incoming(target.doc_id):
        if rel.type in ("amends", "supersedes") and other.effective_date \
                and other.effective_date > secondary.publication_date:
            return True
    return False


def secondary_outdated(corpus: Corpus, doc: Source) -> str | None:
    """Reason a secondary source is outdated, or None."""
    if doc.role.value != "secondary":
        return None
    for r in doc.relations:
        t = corpus.sources.get(r.target)
        if r.type == "describes" and t and _published_before_change(corpus, doc, t):
            return (f"published {doc.publication_date}, before a later amendment/replacement of "
                    f"'{t.title}' took effect")
    return None


def detect_conflicts(corpus: Corpus, chunks: list[tuple[Chunk, str]], query_topics: set[str],
                     statuses: dict[str, str]) -> list[Conflict]:
    """Flag unrelated primary provisions on the same topic that state different numbers for the same unit.

    `chunks` is a list of (chunk, doc_status). Documents linked by an amendment/supersession/clarification
    relation are NOT conflicts - that is version information (see build_version_notes).
    """
    out: list[Conflict] = []
    seen: set[tuple[str, str]] = set()
    for i, (a, _) in enumerate(chunks):
        for b, _ in chunks[i + 1:]:
            if a.doc_id == b.doc_id or (a.doc_id, b.doc_id) in seen:
                continue
            sa, sb = corpus.sources[a.doc_id], corpus.sources[b.doc_id]
            if sa.role.value != "primary" or sb.role.value != "primary":
                continue
            if b.doc_id in corpus.related_doc_ids(a.doc_id):
                continue
            if statuses.get(a.chunk_id) != "in_force" or statuses.get(b.chunk_id) != "in_force":
                continue
            shared_topics = topics_of(a.text) & topics_of(b.text) & query_topics
            if not shared_topics:
                continue
            qa_, qb_ = quantities(a.text), quantities(b.text)
            diffs = [(u, qa_[u], qb_[u]) for u in qa_.keys() & qb_.keys() if qa_[u] != qb_[u]]
            if not diffs:
                continue
            seen.add((a.doc_id, b.doc_id))
            u, va, vb = diffs[0]
            hint = ""
            if sa.jurisdiction != sb.jurisdiction:
                hint = (f" The documents come from different jurisdictions ({sa.jurisdiction} vs "
                        f"{sb.jurisdiction}); whether the narrower rule adds to, displaces or conflicts with the "
                        "wider one is a legal question the system cannot decide.")
            out.append(Conflict(
                topic=sorted(shared_topics)[0], doc_a=a.doc_id, doc_b=b.doc_id,
                chunk_a=a.chunk_id, chunk_b=b.chunk_id,
                description=(f"'{sa.title}' {a.section} states {u}={sorted(va)}, but '{sb.title}' {b.section} "
                             f"states {u}={sorted(vb)}. Neither document is marked as amending the other." + hint)))
    return out

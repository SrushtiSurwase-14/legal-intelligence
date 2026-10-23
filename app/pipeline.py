"""The controlled research path:
question analysis -> source discovery -> source validation -> retrieval/selection
-> version resolution -> evidence extraction -> (limitations, status, confidence).
Every step is timed and recorded in `steps`; nothing fails silently.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date

from .config import Settings
from .fallbacks import make_limitation
from .ingestion import Corpus
from .logging_config import new_trace_id, reset_trace_id, set_trace_id
from .models import (CandidateSource, Conflict, Evidence, FailureCode as F, Limitation, QuestionAnalysis,
                     ResearchRequest, Role, Status, StepRecord, VersionNote)
from .question import analyze_question
from .retrieval import Hit, Retriever
from .textutil import index_stems, pick_sentences, query_terms, topics_of
from .versioning import (AsOf, build_version_notes, detect_conflicts, provision_status, secondary_outdated)

log = logging.getLogger("li.pipeline")
STEP_NAMES = ["question_analysis", "source_discovery", "source_validation", "retrieval_selection",
              "version_resolution", "evidence_extraction"]
RISK_QUERY = "penalty fine punishable contravenes offence"


@dataclass
class PipelineState:
    trace_id: str
    request: ResearchRequest
    today: date
    qa: QuestionAnalysis | None = None
    status: Status = Status.ANSWERED
    steps: list[StepRecord] = field(default_factory=list)
    limitations: list[Limitation] = field(default_factory=list)
    candidates: list[CandidateSource] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    version_notes: list[VersionNote] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    confidence: str = "none"
    confidence_basis: list[str] = field(default_factory=list)
    secondary_only: bool = False
    terminal: bool = False

    def add(self, code: F, detail: str = "", severity: str | None = None) -> Limitation:
        lim = make_limitation(code, detail, severity)
        self.limitations.append(lim)
        return lim

    def codes(self) -> set[F]:
        return {l.code for l in self.limitations}


class ResearchPipeline:
    def __init__(self, corpus: Corpus, retriever: Retriever, settings: Settings, today: date | None = None):
        self.corpus, self.retriever, self.settings = corpus, retriever, settings
        self.today = today or settings.today or date.today()

    # ------------------------------------------------------------ helpers
    def _record(self, st: PipelineState, name: str, status: str, detail: str, t0: float) -> None:
        st.steps.append(StepRecord(name=name, status=status, detail=detail,  # type: ignore[arg-type]
                                   duration_ms=round((time.perf_counter() - t0) * 1000, 2)))
        log.info("step=%s status=%s %s", name, status, detail)

    def _finish_early(self, st: PipelineState, status: Status) -> PipelineState:
        done = {s.name for s in st.steps}
        for n in STEP_NAMES:
            if n not in done:
                st.steps.append(StepRecord(name=n, status="skipped", detail="earlier step ended the run"))
        st.status, st.terminal, st.confidence = status, True, "none"
        return st

    # ------------------------------------------------------------ main
    def run(self, req: ResearchRequest, trace_id: str | None = None) -> PipelineState:
        st = PipelineState(trace_id=trace_id or new_trace_id(), request=req, today=self.today)
        token = set_trace_id(st.trace_id)
        try:
            return self._run(st)
        finally:
            reset_trace_id(token)

    def _run(self, st: PipelineState) -> PipelineState:
        req, c, cfg = st.request, self.corpus, self.settings
        top_k = req.top_k or cfg.top_k

        # 1. question analysis ---------------------------------------------------------
        t0 = time.perf_counter()
        qa = analyze_question(req, c.tree, self.today)
        st.qa = qa
        self._record(st, "question_analysis", "ok" if qa.valid else "failed",
                     "; ".join(qa.issues) or f"topics={qa.topics} jurisdiction={qa.jurisdiction} "
                                              f"as_of={qa.as_of_description}", t0)
        if not qa.valid:
            st.add(F.MALFORMED_QUESTION, "; ".join(qa.issues))
            return self._finish_early(st, Status.MALFORMED_QUESTION)
        if qa.jurisdiction_unrecognised:
            names = ", ".join(c.tree.names) or "none"
            st.add(F.AMBIGUOUS_JURISDICTION, f"Jurisdiction '{qa.jurisdiction_unrecognised}' is not covered by "
                                             f"the document set (covered: {names}).", severity="blocking")
            return self._finish_early(st, Status.INSUFFICIENT_EVIDENCE)

        allowed: set[str] | None = None
        if qa.jurisdiction:
            applicable = set(c.tree.applicable(qa.jurisdiction))
            allowed = {d for d, s in c.sources.items() if s.jurisdiction in applicable}
        asof = AsOf(qa.as_of_date, qa.as_of_year, qa.as_of_assumed)

        # 2. source discovery ----------------------------------------------------------
        t0 = time.perf_counter()
        try:
            hits = self.retriever.search(qa.raw, k=top_k * 3, allowed_docs=allowed,
                                         exclude_terms=tuple(qa.exclude_terms))
        except Exception as e:  # noqa: BLE001 - dependency failure must be visible, never hidden
            self._record(st, "source_discovery", "failed", f"{e.__class__.__name__}: {e}", t0)
            st.add(F.RETRIEVAL_FAILURE, f"({e.__class__.__name__}: {e})")
            return self._finish_early(st, Status.ERROR)
        qa.search_terms = query_terms(qa.raw, qa.exclude_terms)
        self._record(st, "source_discovery", "ok", f"{len(hits)} candidate chunks for terms {qa.search_terms}", t0)
        if not hits:
            st.add(F.NO_SOURCE_FOUND)
            return self._finish_early(st, Status.INSUFFICIENT_EVIDENCE)

        # 3. source validation ---------------------------------------------------------
        t0 = time.perf_counter()
        doc_order: list[str] = []
        for h in hits:
            if h.chunk.doc_id not in doc_order:
                doc_order.append(h.chunk.doc_id)
        unavailable: dict[str, str] = {}
        for d in doc_order:
            ok, why = c.verify_available(d)
            if not ok:
                unavailable[d] = why
        for d in doc_order:
            dh = [h for h in hits if h.chunk.doc_id == d]
            st.candidates.append(CandidateSource(
                source=c.sources[d], best_score=max(h.score for h in dh), best_coverage=max(h.coverage for h in dh),
                availability="unavailable" if d in unavailable else "available"))
        hits = [h for h in hits if h.chunk.doc_id not in unavailable]
        for d, why in unavailable.items():
            st.add(F.SOURCE_UNAVAILABLE, f"'{c.sources[d].title}': {why}.",
                   severity="warning" if hits else "blocking")
        self._record(st, "source_validation", "ok" if not unavailable else "failed",
                     f"{len(doc_order) - len(unavailable)} available, {len(unavailable)} unavailable", t0)
        if not hits:
            return self._finish_early(st, Status.INSUFFICIENT_EVIDENCE)

        # 4. retrieval selection (quality gate) ----------------------------------------
        t0 = time.perf_counter()
        top = hits[0]
        top_cov = max(h.coverage for h in hits)
        strong = [h for h in hits if h.coverage >= cfg.min_coverage and h.score >= cfg.min_score
                  and h.score >= cfg.relative_score_cutoff * top.score
                  and h.coverage >= cfg.relative_coverage_cutoff * top_cov]
        by_doc = {cand.source.doc_id: cand for cand in st.candidates}
        if not strong:
            for cand in st.candidates:
                cand.selection_reason = "match too weak to be used as evidence"
            st.add(F.POOR_RETRIEVAL, f"Best match covered {top.coverage:.0%} of the question's terms "
                                     f"(minimum {cfg.min_coverage:.0%}).")
            self._record(st, "retrieval_selection", "failed", "no chunk passed the quality gate", t0)
            return self._finish_early(st, Status.INSUFFICIENT_EVIDENCE)
        primary = [h for h in strong if c.sources[h.chunk.doc_id].role == Role.PRIMARY]
        if primary:
            selected = primary[:top_k]
            for h in strong:
                if h not in selected and c.sources[h.chunk.doc_id].role == Role.SECONDARY:
                    cand = by_doc[h.chunk.doc_id]
                    cand.selection_reason = "secondary source kept as context only; primary authority available"
        else:
            selected = strong[:top_k]
            st.secondary_only = True
            st.add(F.SECONDARY_ONLY)
        for cand in st.candidates:
            if not cand.selection_reason:
                cand.selection_reason = "ranked below the selected sources or below the quality gate"
        for h in selected:
            cand = by_doc[h.chunk.doc_id]
            cand.selected = True
            cand.selection_reason = (f"{cand.source.role.value} source; best match score {cand.best_score}, "
                                     f"coverage {cand.best_coverage:.0%}")
        self._record(st, "retrieval_selection", "ok", f"{len(selected)} chunks selected from "
                     f"{len({h.chunk.doc_id for h in selected})} documents", t0)

        # 5. version resolution --------------------------------------------------------
        t0 = time.perf_counter()
        selected = self._expand_versions(st, selected, qa, allowed, by_doc)
        doc_ids = list(dict.fromkeys(h.chunk.doc_id for h in selected))
        st.version_notes = build_version_notes(c, doc_ids, asof)
        statuses: dict[str, tuple[str, str, str | None]] = {}
        for h in selected:
            statuses[h.chunk.chunk_id] = provision_status(c, c.sources[h.chunk.doc_id], h.chunk.section_id, asof)
        for cand in st.candidates:
            reason = secondary_outdated(c, cand.source)
            if reason:
                cand.flags.append("outdated: " + reason)
                if cand.selected:
                    st.add(F.OUTDATED_SOURCE, f"'{cand.source.title}' is {reason}.")
        st.conflicts = detect_conflicts(
            c, [(h.chunk, statuses[h.chunk.chunk_id][0]) for h in selected if h.via == "search"],
            set(qa.topics), {k: v[0] for k, v in statuses.items()})
        if st.conflicts:
            st.add(F.CONFLICTING_SOURCES, f"{len(st.conflicts)} conflict(s) found.")
        self._record(st, "version_resolution", "ok",
                     f"{len(st.version_notes)} version note(s), {len(st.conflicts)} conflict(s)", t0)

        # 6. evidence extraction -------------------------------------------------------
        t0 = time.perf_counter()
        self._extract_evidence(st, selected, qa, statuses, by_doc)
        self._record(st, "evidence_extraction", "ok" if st.evidence else "failed",
                     f"{len(st.evidence)} verified quote(s)", t0)
        if not st.evidence:
            return self._finish_early(st, Status.INSUFFICIENT_EVIDENCE)

        self._post_checks(st, selected, asof)
        return st

    # ------------------------------------------------------------ pieces
    def _expand_versions(self, st, selected: list[Hit], qa, allowed, by_doc) -> list[Hit]:
        """Pull in the amending/replacing (or amended) document so the relationship is visible."""
        c = self.corpus
        have = {h.chunk.doc_id for h in selected}
        out = list(selected)
        for h in list(selected):
            d = h.chunk.doc_id
            wanted: list[tuple[str, list[str]]] = []
            sel_secs = {x.chunk.section_id for x in selected if x.chunk.doc_id == d}
            for other, rel in c.incoming(d):
                if rel.type in ("amends", "supersedes", "clarifies") and (
                        not rel.affected_sections or sel_secs & set(rel.affected_sections)):
                    wanted.append((other.doc_id, []))
            for rel in c.sources[d].relations:
                if rel.type in ("amends", "supersedes", "clarifies") and rel.target in c.sources:
                    wanted.append((rel.target, rel.affected_sections))
            for other_id, sections in wanted:
                if other_id in have or (allowed is not None and other_id not in allowed):
                    continue
                ok, why = c.verify_available(other_id)
                if not ok:
                    st.add(F.SOURCE_UNAVAILABLE, f"'{c.sources[other_id].title}' (related version): {why}.")
                    continue
                cand_hits = self.retriever.search(qa.raw, k=3, allowed_docs={other_id},
                                                  exclude_terms=tuple(qa.exclude_terms))
                if sections:
                    pref = [x for x in cand_hits if x.chunk.section_id in sections]
                    cand_hits = pref or [x for x in (self._chunk_hit(other_id, s) for s in sections) if x]
                if not cand_hits:
                    cand_hits = [x for x in [self._first_operative(other_id)] if x]
                if not cand_hits:
                    continue
                eh = cand_hits[0]
                eh.via = "version_expansion"
                out.append(eh)
                have.add(other_id)
                cand = by_doc.get(other_id)
                if cand is None:
                    cand = CandidateSource(source=c.sources[other_id], best_score=eh.score,
                                           best_coverage=eh.coverage)
                    st.candidates.append(cand)
                    by_doc[other_id] = cand
                cand.selected = True
                cand.selection_reason = (f"included to expose its version relationship with "
                                         f"'{c.sources[d].title}' (not chosen by score)")
        return out

    def _chunk_hit(self, doc_id: str, section_id: str) -> Hit | None:
        for ch in self.corpus.chunks:
            if ch.doc_id == doc_id and ch.section_id == section_id:
                return Hit(ch, 0.0, 0.0, [], "version_expansion")
        return None

    def _first_operative(self, doc_id: str) -> Hit | None:
        for ch in self.corpus.chunks:
            if ch.doc_id == doc_id and ch.section_id:
                return Hit(ch, 0.0, 0.0, [], "version_expansion")
        return None

    def _extract_evidence(self, st, selected: list[Hit], qa, statuses, by_doc) -> None:
        c = self.corpus
        terms = qa.search_terms

        def make(h: Hit, purpose: str) -> Evidence | None:
            src = c.sources[h.chunk.doc_id]
            span = pick_sentences(h.chunk.text, terms)
            if span is None:
                return None
            quote = h.chunk.text[span[0]:span[1]].strip()
            cs = h.chunk.start + span[0] + (len(h.chunk.text[span[0]:span[1]]) - len(h.chunk.text[span[0]:span[1]].lstrip()))
            ce = cs + len(quote)
            try:
                live = c.read_text(src.doc_id)
            except OSError:
                live = ""
            verified = live[cs:ce] == quote
            if not verified:
                st.add(F.EVIDENCE_UNVERIFIED, f"Quote from '{src.title}' {h.chunk.section} was discarded.")
                return None
            stat, note, rel = (statuses.get(h.chunk.chunk_id)
                               or provision_status(c, src, h.chunk.section_id,
                                                   AsOf(qa.as_of_date, qa.as_of_year, qa.as_of_assumed)))
            return Evidence(evidence_id="", doc_id=src.doc_id, title=src.title, chunk_id=h.chunk.chunk_id,
                            section=h.chunk.section, section_id=h.chunk.section_id, quote=quote,
                            char_start=cs, char_end=ce, score=h.score, coverage=h.coverage, role=src.role,
                            verified=True, purpose=purpose,  # type: ignore[arg-type]
                            provision_status=stat, status_note=note, related_doc_id=rel,  # type: ignore[arg-type]
                            source_url=src.source_url, version=src.version, jurisdiction=src.jurisdiction)

        answer = sorted([h for h in selected if h.via == "search"], key=lambda h: -h.score)
        context = [h for h in selected if h.via != "search"]
        items: list[Evidence] = []
        for h in answer:
            e = make(h, "answer")
            if e:
                items.append(e)
        for h in context:
            e = make(h, "version_context")
            if e:
                items.append(e)
        # risk / penalty provisions from the same primary documents
        if qa.topics and "penalty" not in qa.topics and items:
            prim_docs = {e.doc_id for e in items if e.role == Role.PRIMARY}
            if prim_docs:
                try:
                    rhits = self.retriever.search(RISK_QUERY, k=6, allowed_docs=prim_docs)
                    taken: set[str] = set()
                    for h in rhits:
                        if "penalty" in topics_of(h.chunk.text) and h.chunk.doc_id not in taken \
                                and h.chunk.chunk_id not in {e.chunk_id for e in items}:
                            e = make(Hit(h.chunk, h.score, h.coverage, h.matched_terms, "risk"), "risk")
                            if e:
                                items.append(e)
                                taken.add(h.chunk.doc_id)
                except Exception as ex:  # noqa: BLE001
                    st.add(F.RETRIEVAL_FAILURE, f"Penalty lookup failed ({ex.__class__.__name__}).",
                           severity="warning")
        for i, e in enumerate(items, 1):
            e.evidence_id = f"E{i}"
        st.evidence = items

    def _post_checks(self, st: PipelineState, selected: list[Hit], asof: AsOf) -> None:
        qa, c = st.qa, self.corpus
        assert qa is not None
        # superseded text: info if its replacement is among the evidence, warning otherwise
        present = {e.doc_id for e in st.evidence}
        flagged: set[str] = set()
        for e in st.evidence:
            if e.provision_status in ("superseded_by_amendment", "superseded", "superseded_replacement_unknown") \
                    and e.doc_id not in flagged:
                flagged.add(e.doc_id)
                if e.related_doc_id and e.related_doc_id in present:
                    st.add(F.OUTDATED_SOURCE, f"'{e.title}' {e.section} is shown for comparison only; its "
                                              f"replacement is also in the evidence.", severity="info")
                else:
                    st.add(F.OUTDATED_SOURCE, f"'{e.title}' {e.section} is superseded and no replacement text "
                                              "was found.", severity="warning")
        # jurisdiction
        if qa.jurisdiction is None and len(c.tree.names) > 1:
            st.missing_facts.append("jurisdiction (which country/province applies to you)")
            juris = sorted({e.jurisdiction for e in st.evidence})
            st.add(F.AMBIGUOUS_JURISDICTION, f"No jurisdiction was given; sources found for: {', '.join(juris)}.")
        # missing facts (applicability questions only)
        facts = st.qa.facts_provided
        if qa.is_applicability:
            if "registration" in qa.topics and "employee_count" not in facts:
                st.missing_facts.append("number of persons employed (employee_count)")
            if "overtime" in qa.topics and "hours_worked" not in facts:
                st.missing_facts.append("hours actually worked per day (hours_worked)")
        if st.missing_facts:
            st.add(F.MISSING_FACTS, "Missing: " + "; ".join(st.missing_facts) + ".")
        if qa.seeks_legal_conclusion:
            st.add(F.UNSUPPORTED_CONCLUSION)
        self._finalise(st)

    def _finalise(self, st: PipelineState) -> None:
        finalise(st)


def finalise(st: PipelineState) -> None:
    """Deterministic status and confidence (no model involved)."""
    if True:
        warn = [l for l in st.limitations if l.severity == "warning"]
        st.status = Status.PARTIAL if warn else Status.ANSWERED
        points, basis = 0, []
        low_codes = {F.CONFLICTING_SOURCES, F.SECONDARY_ONLY, F.UNSUPPORTED_CONCLUSION}
        for l in st.limitations:
            if l.severity == "warning":
                if l.code in low_codes:
                    points += 3
                    basis.append(f"{l.code.value} lowers confidence strongly")
                else:
                    points += 1
                    basis.append(f"{l.code.value} lowers confidence")
        best_cov = max((e.coverage for e in st.evidence if e.purpose == "answer"), default=0.0)
        if best_cov < 0.5:
            points += 1
            basis.append(f"best evidence matches only {best_cov:.0%} of the question's terms")
        if not basis:
            basis.append("primary evidence, verified quotes, no conflicts, no missing facts")
        st.confidence = "low" if points >= 3 else "medium" if points >= 1 else "high"
        st.confidence_basis = basis

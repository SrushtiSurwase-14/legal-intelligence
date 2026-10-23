"""Day 4 - turn evidence into the structured legal analysis.

Two analyzers share one rule: *only retrieved evidence may support a statement*.
- ExtractiveAnalyzer: deterministic, quotes + rule-based interpretation (default, works offline).
- LLMAnalyzer: asks a model for narrative statements, then VALIDATES them (known evidence ids, numbers
  grounded in evidence, no certainty language). Invalid output is rejected -> extractive fallback + MODEL_FAILURE.
"""
from __future__ import annotations

import json
import logging
import re

from .fallbacks import make_limitation
from .llm import LLMClient, LLMUnavailable
from .models import (Evidence, FailureCode as F, Label, LegalAnalysis, Provision, Role, SourceRef, Statement)
from .pipeline import PipelineState, finalise
from .textutil import topics_of

log = logging.getLogger("li.analysis")

_OVERCLAIM = re.compile(r"\b(definitely|certainly|guaranteed?|undoubtedly|without (?:any )?doubt|100%|"
                        r"unquestionably|beyond doubt|will (?:surely|certainly))\b", re.I)
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_THRESHOLD = re.compile(r"(\d+)\s+or\s+more\s+(?:persons|employees|workers)", re.I)


class ModelOutputInvalid(ValueError):
    pass


def _src_refs(st: PipelineState, corpus) -> list[SourceRef]:
    used: dict[str, str] = {}
    for e in st.evidence:
        used.setdefault(e.doc_id, {"answer": "evidence", "version_context": "version context",
                                   "risk": "risk/penalty provision"}[e.purpose])
    out = []
    for cand in st.candidates:
        s = cand.source
        if s.doc_id in used:
            u = used[s.doc_id]
        elif cand.availability == "unavailable":
            u = "unavailable (not used)"
        else:
            u = "candidate only (not used as evidence)"
        out.append(SourceRef(doc_id=s.doc_id, title=s.title, role=s.role, jurisdiction=s.jurisdiction,
                             document_type=s.document_type, issuing_authority=s.issuing_authority,
                             publication_date=s.publication_date, effective_date=s.effective_date,
                             amendment_status=s.amendment_status, version=s.version, source_url=s.source_url,
                             retrieval_date=s.retrieval_date, used_as=u))
    return out


def _cite(e: Evidence) -> str:
    return f"{e.title}, {e.section} (version {e.version})"


class ExtractiveAnalyzer:
    name = "extractive"

    def analyze(self, st: PipelineState, corpus) -> LegalAnalysis:
        qa = st.qa
        stmts = self.evidence_statements(st) + self.safety_statements(st)
        return self._assemble(st, corpus, stmts, generated_by="extractive")

    # -- deterministic building blocks (also reused around LLM output)
    def evidence_statements(self, st: PipelineState) -> list[Statement]:
        out: list[Statement] = []
        for e in st.evidence:
            if e.purpose == "risk":
                continue
            tag = " [secondary, non-authoritative]" if e.role == Role.SECONDARY else ""
            if e.provision_status == "in_force":
                out.append(Statement(text=f"{_cite(e)}{tag} states: \"{e.quote}\"", label=Label.VERIFIED,
                                     evidence_ids=[e.evidence_id]))
            elif e.provision_status in ("superseded_by_amendment", "superseded"):
                ids = [e.evidence_id]
                rep = [x.evidence_id for x in st.evidence if x.doc_id == e.related_doc_id]
                out.append(Statement(
                    text=f"{_cite(e)} reads \"{e.quote}\" - note: {e.status_note}"
                         + (f" The replacing text is in {', '.join(rep)}." if rep else ""),
                    label=Label.SOURCE_DERIVED, evidence_ids=ids + rep))
            elif e.provision_status == "not_yet_in_force":
                out.append(Statement(text=f"{_cite(e)} reads \"{e.quote}\" - note: {e.status_note}",
                                     label=Label.SOURCE_DERIVED, evidence_ids=[e.evidence_id]))
            else:  # uncertain_timing / replacement unknown
                out.append(Statement(text=f"{_cite(e)} reads \"{e.quote}\" - {e.status_note}",
                                     label=Label.UNCERTAIN, evidence_ids=[e.evidence_id]))
        out += self._applicability(st)
        return out

    def _applicability(self, st: PipelineState) -> list[Statement]:
        qa, out = st.qa, []
        n = qa.facts_provided.get("employee_count")
        if n is None or "registration" not in qa.topics:
            return out
        try:
            n = int(n)
        except (TypeError, ValueError):
            return out
        for e in st.evidence:
            if e.provision_status != "in_force" or e.purpose == "risk":
                continue
            m = _THRESHOLD.search(e.quote)
            if m:
                t = int(m.group(1))
                verdict = "meets" if n >= t else "does not meet"
                out.append(Statement(
                    text=f"If {e.title} applies to you, an establishment with {n} persons {verdict} the registration "
                         f"threshold of {t} persons stated in {e.section}. (Whether that instrument applies to your "
                         "situation is a legal question; this is a mechanical comparison only.)",
                    label=Label.INTERPRETATION, evidence_ids=[e.evidence_id]))
        return out

    def safety_statements(self, st: PipelineState) -> list[Statement]:
        out: list[Statement] = []
        for c in st.conflicts:
            ids = [e.evidence_id for e in st.evidence if e.chunk_id in (c.chunk_a, c.chunk_b)]
            out.append(Statement(text=c.description + " " + c.resolution, label=Label.CONFLICTING, evidence_ids=ids))
        for m in st.missing_facts:
            out.append(Statement(text=f"Not established because this fact is missing: {m}.", label=Label.MISSING))
        codes = st.codes()
        if F.UNSUPPORTED_CONCLUSION in codes:
            out.append(Statement(text="The question asks for an outcome or liability conclusion. The sources can "
                                      "show the relevant provisions but cannot establish how a case would be decided; "
                                      "no such conclusion is given.", label=Label.UNCERTAIN))
        if F.SECONDARY_ONLY in codes:
            out.append(Statement(text="Only secondary (non-authoritative) sources support this; the primary legal "
                                      "text was not found.", label=Label.UNCERTAIN))
        if F.AMBIGUOUS_JURISDICTION in codes:
            out.append(Statement(text="The applicable jurisdiction was not specified, so which source governs your "
                                      "situation is not established.", label=Label.UNCERTAIN))
        return out

    def _assemble(self, st: PipelineState, corpus, stmts: list[Statement], generated_by: str,
                  clear: list[str] | None = None, unclear: list[str] | None = None,
                  next_step: str | None = None) -> LegalAnalysis:
        qa = st.qa
        interp = any(s.label == Label.INTERPRETATION for s in stmts)
        reasons = [l.message for l in st.limitations if l.escalate and l.severity != "info"]
        if interp:
            reasons.append("The analysis applies a rule to your facts (INTERPRETATION).")
        if st.confidence in ("low", "none"):
            reasons.append(f"Confidence is {st.confidence}.")
        review = bool(reasons)

        if not st.evidence:
            block = next((l for l in st.limitations if l.severity == "blocking"), None)
            stmts = stmts or []
            stmts.insert(0, Statement(text="No evidence-backed conclusion can be given. "
                                           + (block.message if block else ""), label=Label.UNCERTAIN))

        if clear is None:
            clear = [f"{_cite(e)}: \"{e.quote}\"" for e in st.evidence
                     if e.provision_status == "in_force" and e.role == Role.PRIMARY and e.purpose != "risk"]
            for n in st.version_notes:
                if n.relation in ("amends", "supersedes", "clarifies") and n.as_of_state == "effective":
                    clear.append(n.message)
            if st.conflicts or st.secondary_only:
                clear = [] if st.secondary_only else clear
        if unclear is None:
            unclear = [c.description for c in st.conflicts]
            unclear += [f"Missing fact: {m}" for m in st.missing_facts]
            unclear += [l.message for l in st.limitations
                        if l.code in (F.UNSUPPORTED_CONCLUSION, F.SECONDARY_ONLY, F.AMBIGUOUS_JURISDICTION,
                                      F.OUTDATED_SOURCE, F.SOURCE_UNAVAILABLE, F.POOR_RETRIEVAL,
                                      F.NO_SOURCE_FOUND) and l.severity != "info"]
            unclear += [n.message for n in st.version_notes if n.as_of_state in ("ambiguous", "unknown")]

        if next_step is None:
            steps = list(dict.fromkeys(l.next_step for l in st.limitations if l.next_step and l.severity != "info"))
            next_step = " ".join(steps) if steps else (
                "Check the quoted provisions against the official published text before relying on them.")

        risks = [e for e in st.evidence if e.purpose == "risk"]
        if risks:
            risk = " ".join(f"{_cite(e)}: \"{e.quote}\" [{e.evidence_id}] (whether this applies to you is not established)."
                            for e in risks)
        elif st.evidence:
            risk = ("No penalty or restriction provision was found in the retrieved documents. "
                    "Absence from this limited document set does not mean none exists.")
        else:
            risk = "Not assessed: no evidence was established."

        provisions = [Provision(evidence_id=e.evidence_id, doc_id=e.doc_id, title=e.title, section=e.section,
                                quote=e.quote, status=e.provision_status, status_note=e.status_note)
                      for e in st.evidence if e.purpose != "risk"]
        return LegalAnalysis(
            question=qa.raw, facts_provided=qa.facts_provided, facts_missing=list(st.missing_facts),
            relevant_sources=_src_refs(st, corpus), applicable_provisions=provisions, analysis=stmts,
            what_is_clear=clear, what_is_unclear=unclear, risk_restriction=risk, recommended_next_step=next_step,
            requires_professional_review=review, review_reasons=list(dict.fromkeys(reasons)),
            confidence=st.confidence, confidence_basis=st.confidence_basis,  # type: ignore[arg-type]
            generated_by=generated_by)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- LLM mode
SYSTEM_PROMPT = (
    "You are a careful legal research assistant. You may ONLY use the numbered evidence supplied. "
    "Never use outside knowledge. Never state a conclusion as certain. If the evidence does not establish "
    "something, say so. Respond with a single JSON object and nothing else.")


def build_prompt(st: PipelineState) -> str:
    ev = "\n".join(f"[{e.evidence_id}] ({e.role.value}, {e.provision_status}) {e.title}, {e.section}: \"{e.quote}\""
                   for e in st.evidence)
    notes = "\n".join(f"- {n.message}" for n in st.version_notes) or "- none"
    return (f"QUESTION: {st.qa.raw}\nAS-OF: {st.qa.as_of_description}\nFACTS: {json.dumps(st.qa.facts_provided, default=str)}\n"
            f"EVIDENCE:\n{ev}\nVERSION NOTES:\n{notes}\n\n"
            'Return JSON: {"analysis":[{"text":str,"label":"SOURCE_DERIVED|INTERPRETATION|UNCERTAIN",'
            '"evidence_ids":[ids]}],"what_is_clear":[str],"what_is_unclear":[str],"recommended_next_step":str}\n'
            "Every SOURCE_DERIVED/INTERPRETATION statement must cite evidence ids. Do not invent numbers.")


_REFS = re.compile(r"\bSection\s+\d+[A-Za-z]?|\[?\bE\d+\b\]?|\bParagraph\s+\d+", re.I)


def _numbers(s: str, strip_refs: bool = False) -> set[str]:
    """Numbers in a text. With strip_refs, 'Section 4' / 'E2' style references are not counted as quantities."""
    if strip_refs:
        s = _REFS.sub(" ", s)
    return {m.replace(",", "") for m in _NUM.findall(s)}


def parse_and_validate(raw: str, st: PipelineState) -> dict:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        raise ModelOutputInvalid("no JSON object in model output")
    try:
        data = json.loads(s[i:j + 1])
    except json.JSONDecodeError as e:
        raise ModelOutputInvalid(f"invalid JSON: {e}") from e
    if not isinstance(data.get("analysis"), list) or not data["analysis"]:
        raise ModelOutputInvalid("'analysis' must be a non-empty list")
    known = {e.evidence_id for e in st.evidence}
    allowed_nums: set[str] = set()
    for e in st.evidence:
        allowed_nums |= _numbers(e.quote, True) | _numbers(e.title) | _numbers(e.version)
    allowed_nums |= _numbers(st.qa.raw, True) | _numbers(json.dumps(st.qa.facts_provided, default=str))
    allowed_nums |= _numbers(st.qa.as_of_description)
    for n in st.version_notes:
        allowed_nums |= _numbers(n.message, True)
    for item in data["analysis"]:
        if not isinstance(item, dict) or "text" not in item or "label" not in item:
            raise ModelOutputInvalid("each statement needs 'text' and 'label'")
        if item["label"] not in ("SOURCE_DERIVED", "INTERPRETATION", "UNCERTAIN"):
            raise ModelOutputInvalid(f"label {item['label']!r} not allowed from the model")
        ids = item.get("evidence_ids") or []
        if not set(ids) <= known:
            raise ModelOutputInvalid(f"unknown evidence ids {sorted(set(ids) - known)}")
        if item["label"] != "UNCERTAIN" and not ids:
            raise ModelOutputInvalid("a non-UNCERTAIN statement has no evidence ids")
        if _OVERCLAIM.search(item["text"]):
            raise ModelOutputInvalid("certainty language is not allowed")
        bad = _numbers(item["text"], True) - allowed_nums
        if bad:
            raise ModelOutputInvalid(f"numbers not found in evidence/question: {sorted(bad)}")
    for key in ("what_is_clear", "what_is_unclear"):
        if not isinstance(data.get(key, []), list):
            raise ModelOutputInvalid(f"'{key}' must be a list")
        for t in data.get(key, []):
            if _OVERCLAIM.search(str(t)) or (_numbers(str(t), True) - allowed_nums):
                raise ModelOutputInvalid(f"'{key}' contains ungrounded numbers or certainty language")
    return data


class LLMAnalyzer:
    name = "llm"

    def __init__(self, llm: LLMClient, fallback: ExtractiveAnalyzer | None = None):
        self.llm, self.fallback = llm, fallback or ExtractiveAnalyzer()

    def analyze(self, st: PipelineState, corpus) -> LegalAnalysis:
        if not st.evidence:  # nothing to ask a model about; never let it answer from memory
            return self.fallback.analyze(st, corpus)
        try:
            raw = self.llm.complete(SYSTEM_PROMPT, build_prompt(st))
            data = parse_and_validate(raw, st)
        except (LLMUnavailable, ModelOutputInvalid) as e:
            log.warning("LLM analysis rejected: %s", e)
            st.add(F.MODEL_FAILURE, f"({e})")
            ex = self.fallback
            # status/confidence must reflect the new limitation
            finalise(st)
            a = ex.analyze(st, corpus)
            a.generated_by = "extractive_fallback"
            return a
        ex = self.fallback
        narrative = [Statement(text=i["text"], label=Label(i["label"]), evidence_ids=i.get("evidence_ids") or [])
                     for i in data["analysis"]]
        verified = [s for s in ex.evidence_statements(st) if s.label == Label.VERIFIED]
        stmts = verified + narrative + ex.safety_statements(st)
        a = ex._assemble(st, corpus, stmts, "llm", clear=None, unclear=None,
                         next_step=None)
        extra_clear = [str(t) for t in data.get("what_is_clear", [])]
        extra_unclear = [str(t) for t in data.get("what_is_unclear", [])]
        a.what_is_clear = a.what_is_clear + [t for t in extra_clear if t not in a.what_is_clear]
        a.what_is_unclear = a.what_is_unclear + [t for t in extra_unclear if t not in a.what_is_unclear]
        if data.get("recommended_next_step") and not _OVERCLAIM.search(str(data["recommended_next_step"])):
            a.recommended_next_step = a.recommended_next_step + " Model suggestion: " + str(data["recommended_next_step"])
        return a

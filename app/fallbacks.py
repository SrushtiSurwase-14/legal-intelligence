"""Day 5 - the failure policy table: what the system does in each failure situation.

docs/failure_matrix.md is generated from this table (scripts/make_failure_matrix.py) and a test checks it
is up to date, so the documentation cannot drift from the implementation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import FailureCode as F
from .models import Limitation


@dataclass(frozen=True)
class FailurePolicy:
    code: F
    situation: str
    severity: str     # info | warning | blocking  (blocking => no conclusion is produced)
    behaviour: str
    message: str
    next_step: str
    escalate: bool


POLICY: dict[F, FailurePolicy] = {p.code: p for p in [
    FailurePolicy(F.NO_SOURCE_FOUND, "No source found", "blocking",
                  "Stop. No evidence, no conclusion. Report that nothing relevant exists in the document set.",
                  "No relevant provision was found in the available documents.",
                  "Rephrase the question, name the jurisdiction/instrument, or consult the official source or a legal professional.",
                  True),
    FailurePolicy(F.SOURCE_UNAVAILABLE, "Source unavailable", "warning",
                  "Drop the unreadable/changed source, keep evidence from the rest, and say which source was lost. "
                  "If nothing is left, stop with no conclusion.",
                  "A source document could not be read or has changed since indexing.",
                  "Retry later; check the document store; do not rely on the missing source.", False),
    FailurePolicy(F.CONFLICTING_SOURCES, "Conflicting sources", "warning",
                  "Show both provisions side by side, do not pick a winner, lower confidence, require review.",
                  "Sources state different values and are not linked by an amendment.",
                  "Have a qualified person determine which provision prevails for your facts.", True),
    FailurePolicy(F.POOR_RETRIEVAL, "Poor retrieval", "blocking",
                  "Stop. Weak matches are listed as candidates but never used as evidence.",
                  "Only weak matches were found; they are not reliable evidence.",
                  "Add detail (instrument name, topic words) or consult the official source.", True),
    FailurePolicy(F.MALFORMED_QUESTION, "Malformed question", "blocking",
                  "Stop before retrieval and explain what is wrong with the question.",
                  "The question could not be analysed.", "Ask a complete question in at least a few words.", False),
    FailurePolicy(F.MISSING_FACTS, "Missing facts", "warning",
                  "Answer what the evidence supports, list the missing facts, do not apply rules to unknown facts.",
                  "Facts needed to apply the law to your situation were not provided.",
                  "Provide the missing facts listed in 'facts_missing'.", False),
    FailurePolicy(F.MODEL_FAILURE, "Model failure", "warning",
                  "Discard unusable LLM output, fall back to the deterministic extractive analysis, and say so.",
                  "The language model was unavailable or returned output that failed validation; "
                  "a deterministic evidence-only analysis was used instead.",
                  "Retry later for a fuller narrative; the cited evidence above is unaffected.", False),
    FailurePolicy(F.UNSUPPORTED_CONCLUSION, "Unsupported legal conclusion", "warning",
                  "Show the relevant provisions but refuse to predict outcomes or declare liability.",
                  "The question asks for an outcome or legal conclusion that the retrieved sources cannot establish.",
                  "Consult a qualified lawyer about your specific case.", True),
    FailurePolicy(F.OUTDATED_SOURCE, "Outdated source", "warning",
                  "Flag the source as outdated; use it only for context; prefer the replacing document if present.",
                  "A source used is outdated or superseded.",
                  "Confirm the current text in the official gazette.", True),
    FailurePolicy(F.AMBIGUOUS_JURISDICTION, "Ambiguous jurisdiction", "warning",
                  "Show sources from every plausible jurisdiction, flag the ambiguity, ask for the jurisdiction. "
                  "If the stated jurisdiction is not covered at all, stop with no conclusion.",
                  "The jurisdiction is missing or not covered, so applicability cannot be confirmed.",
                  "State the jurisdiction (country / province) that applies to you.", True),
    FailurePolicy(F.RETRIEVAL_FAILURE, "Retriever/dependency failure", "blocking",
                  "Return status 'error' with the failing step visible. Never fall back to model memory.",
                  "The retrieval component failed.", "Retry later; check service logs using the trace_id.", False),
    FailurePolicy(F.EVIDENCE_UNVERIFIED, "Evidence not verifiable", "warning",
                  "Discard any quote that cannot be matched verbatim to the live source text.",
                  "A quote could not be verified against the source text and was discarded.",
                  "Re-index the documents and retry.", False),
    FailurePolicy(F.SECONDARY_ONLY, "Only secondary sources", "warning",
                  "Show them as context, cap confidence at 'low', require review.",
                  "Only non-authoritative (secondary) sources were found.",
                  "Locate the primary legal text (Act, rules, notification) before relying on this.", True),
    FailurePolicy(F.INTERNAL_ERROR, "Unexpected internal error", "blocking",
                  "Return status 'error' with a trace_id; never return a partial guess.",
                  "An unexpected error occurred.", "Retry; report the trace_id to the maintainers.", False),
]}


def make_limitation(code: F, detail: str = "", severity: str | None = None) -> Limitation:
    p = POLICY[code]
    msg = p.message + (f" {detail}" if detail else "")
    return Limitation(code=code, severity=severity or p.severity, message=msg,  # type: ignore[arg-type]
                      next_step=p.next_step, escalate=p.escalate)

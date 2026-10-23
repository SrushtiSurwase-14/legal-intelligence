"""All data shapes (the 'contracts'): sources, evidence, analysis, API requests/responses."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    PRIMARY = "primary"      # the law / notification / order itself
    SECONDARY = "secondary"  # commentary, blogs, news - context only


class Label(str, Enum):
    """Epistemic label attached to every analysis statement (task Rule 3)."""
    VERIFIED = "VERIFIED"                # verbatim quote re-checked against the source text
    SOURCE_DERIVED = "SOURCE_DERIVED"    # follows directly from source text / metadata
    INTERPRETATION = "INTERPRETATION"    # applying a rule to the user's facts - needs review
    UNCERTAIN = "UNCERTAIN"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class FailureCode(str, Enum):
    NO_SOURCE_FOUND = "NO_SOURCE_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    POOR_RETRIEVAL = "POOR_RETRIEVAL"
    MALFORMED_QUESTION = "MALFORMED_QUESTION"
    MISSING_FACTS = "MISSING_FACTS"
    MODEL_FAILURE = "MODEL_FAILURE"
    UNSUPPORTED_CONCLUSION = "UNSUPPORTED_CONCLUSION"
    OUTDATED_SOURCE = "OUTDATED_SOURCE"
    AMBIGUOUS_JURISDICTION = "AMBIGUOUS_JURISDICTION"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    EVIDENCE_UNVERIFIED = "EVIDENCE_UNVERIFIED"
    SECONDARY_ONLY = "SECONDARY_ONLY"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class Status(str, Enum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MALFORMED_QUESTION = "malformed_question"
    ERROR = "error"


# ------------------------------------------------------------------ sources
class Relation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["amends", "supersedes", "clarifies", "describes"]
    target: str
    affected_sections: list[str] = Field(default_factory=list)
    note: str = ""


class Source(BaseModel):
    """Source & version model (Day 3). One record per legal document."""
    model_config = ConfigDict(extra="forbid")
    doc_id: str
    title: str
    jurisdiction: str
    issuing_authority: str
    document_type: str
    publication_date: date
    effective_date: date | None = None
    amendment_status: Literal["original", "amended", "superseded", "amending_instrument",
                              "clarifying_instrument", "not_applicable", "unknown"] = "unknown"
    source_url: str
    version: str
    retrieval_date: date
    role: Role
    relations: list[Relation] = Field(default_factory=list)
    is_synthetic: bool = False
    file: str
    notes: str = ""


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    section: str                 # e.g. "Section 4", "Paragraph 2", "Preamble"
    section_id: str | None = None  # e.g. "4"
    text: str
    start: int                   # character offsets inside the full document text
    end: int


class Evidence(BaseModel):
    evidence_id: str
    doc_id: str
    title: str
    chunk_id: str
    section: str
    section_id: str | None = None
    quote: str
    char_start: int
    char_end: int
    score: float
    coverage: float
    role: Role
    verified: bool
    purpose: Literal["answer", "version_context", "risk"] = "answer"
    provision_status: Literal["in_force", "superseded_by_amendment", "superseded", "not_yet_in_force",
                              "uncertain_timing", "superseded_replacement_unknown"] = "in_force"
    status_note: str = ""
    related_doc_id: str | None = None
    source_url: str
    version: str
    jurisdiction: str


class VersionNote(BaseModel):
    relation: str
    from_doc: str
    to_doc: str
    from_title: str
    to_title: str
    effective_date: date | None
    affected_sections: list[str] = Field(default_factory=list)
    as_of_state: Literal["effective", "not_yet", "ambiguous", "unknown"]
    message: str


class Conflict(BaseModel):
    topic: str
    doc_a: str
    doc_b: str
    chunk_a: str
    chunk_b: str
    description: str
    resolution: str = "NOT RESOLVED by the system: both provisions are shown. Needs professional review."


class Limitation(BaseModel):
    code: FailureCode
    severity: Literal["info", "warning", "blocking"]
    message: str
    next_step: str = ""
    escalate: bool = False


class StepRecord(BaseModel):
    name: str
    status: Literal["ok", "failed", "skipped"]
    detail: str = ""
    duration_ms: float = 0.0


class CandidateSource(BaseModel):
    source: Source
    best_score: float
    best_coverage: float
    availability: Literal["available", "unavailable"] = "available"
    selected: bool = False
    selection_reason: str = ""
    flags: list[str] = Field(default_factory=list)


class QuestionAnalysis(BaseModel):
    raw: str
    valid: bool
    issues: list[str] = Field(default_factory=list)
    jurisdiction: str | None = None
    jurisdiction_source: Literal["request", "question_text", "none"] = "none"
    jurisdiction_unrecognised: str | None = None
    as_of_date: date | None = None
    as_of_year: int | None = None
    as_of_assumed: bool = False
    as_of_description: str = ""
    topics: list[str] = Field(default_factory=list)
    is_applicability: bool = False
    seeks_legal_conclusion: bool = False
    facts_provided: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ analysis
class Statement(BaseModel):
    text: str
    label: Label
    evidence_ids: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    doc_id: str
    title: str
    role: Role
    jurisdiction: str
    document_type: str
    issuing_authority: str
    publication_date: date
    effective_date: date | None
    amendment_status: str
    version: str
    source_url: str
    retrieval_date: date
    used_as: str


class Provision(BaseModel):
    evidence_id: str
    doc_id: str
    title: str
    section: str
    quote: str
    status: str
    status_note: str = ""


class LegalAnalysis(BaseModel):
    """Day 4 structured output. Field order mirrors the template in the task brief."""
    question: str
    facts_provided: dict[str, Any]
    facts_missing: list[str]
    relevant_sources: list[SourceRef]
    applicable_provisions: list[Provision]
    analysis: list[Statement]
    what_is_clear: list[str]
    what_is_unclear: list[str]
    risk_restriction: str
    recommended_next_step: str
    requires_professional_review: bool
    review_reasons: list[str] = Field(default_factory=list)
    confidence: Literal["none", "low", "medium", "high"]
    confidence_basis: list[str] = Field(default_factory=list)
    generated_by: Literal["extractive", "llm", "extractive_fallback"] = "extractive"
    disclaimer: str = ("Informational output from a limited document set. Not legal advice. "
                       "Verify against the official text before relying on it.")


# ------------------------------------------------------------------ API
class ResearchRequest(BaseModel):
    question: str = Field(max_length=2000)
    jurisdiction: str | None = Field(default=None, max_length=200)
    as_of_date: date | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    top_k: int | None = Field(default=None, ge=1, le=20)


class SystemInfo(BaseModel):
    app_version: str
    analyzer_mode: str
    retriever: str
    llm_provider: str
    corpus_docs: int
    corpus_chunks: int
    corpus_fingerprint: str
    today: date


class ResearchResponse(BaseModel):
    trace_id: str
    status: Status
    request: ResearchRequest
    question_analysis: QuestionAnalysis | None
    candidate_sources: list[CandidateSource]
    evidence: list[Evidence]
    version_notes: list[VersionNote]
    conflicts: list[Conflict]
    missing_facts: list[str]
    limitations: list[Limitation]
    confidence: Literal["none", "low", "medium", "high"]
    steps: list[StepRecord]
    system: SystemInfo


class AnalyzeResponse(ResearchResponse):
    answer_summary: str
    analysis: LegalAnalysis

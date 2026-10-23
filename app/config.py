"""Configuration: environment variables (optionally from .env) -> an immutable Settings object."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ANALYZER_MODES = {"extractive", "llm"}
RETRIEVERS = {"bm25", "hybrid"}
LLM_PROVIDERS = {"none", "anthropic"}
FAILURES = {None, "retriever", "source", "llm"}


@dataclass(frozen=True)
class Settings:
    corpus_dir: Path = ROOT / "data" / "corpus"
    trace_dir: Path | None = ROOT / "logs"
    analyzer_mode: str = "extractive"
    retriever_kind: str = "bm25"
    llm_provider: str = "none"
    llm_model: str = "claude-sonnet-5-5"
    llm_api_key: str | None = None
    top_k: int = 5
    min_score: float = 0.5
    min_coverage: float = 0.30
    relative_score_cutoff: float = 0.4
    relative_coverage_cutoff: float = 0.6
    simulate_failure: str | None = None
    today: date | None = None
    log_level: str = "INFO"

    def validate(self) -> "Settings":
        if self.analyzer_mode not in ANALYZER_MODES:
            raise ValueError(f"LI_ANALYZER_MODE must be one of {sorted(ANALYZER_MODES)}")
        if self.retriever_kind not in RETRIEVERS:
            raise ValueError(f"LI_RETRIEVER must be one of {sorted(RETRIEVERS)}")
        if self.llm_provider not in LLM_PROVIDERS:
            raise ValueError(f"LI_LLM_PROVIDER must be one of {sorted(LLM_PROVIDERS)}")
        if self.simulate_failure not in FAILURES:
            raise ValueError("LI_SIMULATE_FAILURE must be empty, 'retriever', 'source' or 'llm'")
        if not (1 <= self.top_k <= 20):
            raise ValueError("LI_TOP_K must be between 1 and 20")
        return self

    @classmethod
    def from_env(cls, **overrides) -> "Settings":
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env")
        except ImportError:  # python-dotenv is optional at runtime
            pass
        g = os.environ.get

        def path(v: str | None, default: Path | None) -> Path | None:
            if v is None:
                return default
            if v == "":
                return None
            p = Path(v)
            return p if p.is_absolute() else ROOT / p

        today = g("LI_TODAY") or None
        s = cls(
            corpus_dir=path(g("LI_CORPUS_DIR"), cls.corpus_dir) or cls.corpus_dir,
            trace_dir=path(g("LI_TRACE_DIR"), cls.trace_dir),
            analyzer_mode=(g("LI_ANALYZER_MODE") or "extractive").strip(),
            retriever_kind=(g("LI_RETRIEVER") or "bm25").strip(),
            llm_provider=(g("LI_LLM_PROVIDER") or "none").strip(),
            llm_model=(g("LI_LLM_MODEL") or cls.llm_model).strip(),
            llm_api_key=g("ANTHROPIC_API_KEY") or None,
            top_k=int(g("LI_TOP_K") or 5),
            min_score=float(g("LI_MIN_SCORE") or 0.5),
            min_coverage=float(g("LI_MIN_COVERAGE") or 0.30),
            simulate_failure=(g("LI_SIMULATE_FAILURE") or None),
            today=date.fromisoformat(today) if today else None,
            log_level=(g("LI_LOG_LEVEL") or "INFO").upper(),
        )
        if overrides:
            s = replace(s, **overrides)
        return s.validate()

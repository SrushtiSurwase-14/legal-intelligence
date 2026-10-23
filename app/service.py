"""Service layer: wires corpus + retriever + pipeline + analyzer and builds API responses."""
from __future__ import annotations

import json
import logging
from datetime import date

from . import __version__
from .analysis import ExtractiveAnalyzer, LLMAnalyzer
from .config import Settings
from .fallbacks import make_limitation
from .ingestion import Corpus
from .llm import build_llm
from .logging_config import new_trace_id, setup_logging
from .models import (AnalyzeResponse, FailureCode as F, LegalAnalysis, ResearchRequest, ResearchResponse, Status,
                     SystemInfo)
from .pipeline import PipelineState, ResearchPipeline
from .retrieval import build_retriever

log = logging.getLogger("li.service")


class LegalIntelligenceService:
    def __init__(self, settings: Settings):
        self.settings = settings.validate()
        setup_logging(settings.log_level)
        self.corpus = Corpus(settings.corpus_dir)
        self.corpus.simulate_unavailable = settings.simulate_failure == "source"
        self.retriever = build_retriever(self.corpus, settings.retriever_kind, settings.simulate_failure)
        self.today = settings.today or date.today()
        self.pipeline = ResearchPipeline(self.corpus, self.retriever, settings, self.today)
        self.llm = build_llm(settings)
        mode = "llm" if (settings.analyzer_mode == "llm" or settings.simulate_failure == "llm") else "extractive"
        self.analyzer_mode = mode
        extractive = ExtractiveAnalyzer()
        self.analyzer = LLMAnalyzer(self.llm, extractive) if mode == "llm" else extractive

    @property
    def ready(self) -> bool:
        return bool(self.corpus.sources)

    # ---------------------------------------------------------------- info
    def system_info(self) -> SystemInfo:
        return SystemInfo(app_version=__version__, analyzer_mode=self.analyzer_mode, retriever=self.retriever.name,
                          llm_provider=self.llm.name, corpus_docs=len(self.corpus.sources),
                          corpus_chunks=len(self.corpus.chunks), corpus_fingerprint=self.corpus.fingerprint(),
                          today=self.today)

    def health(self) -> dict:
        problems = list(self.corpus.load_errors)
        if not self.corpus.sources:
            problems.append("no documents loaded")
        deps = {"corpus": "ok" if self.corpus.sources and not self.corpus.load_errors else "degraded",
                "retriever": self.retriever.name,
                "llm": self.llm.name if self.analyzer_mode == "llm" else "not used (extractive mode)"}
        return {"status": "ok" if not problems else "degraded", "version": __version__,
                "dependencies": deps, "problems": problems, "warnings": list(self.corpus.warnings),
                "system": self.system_info().model_dump(mode="json")}

    # ---------------------------------------------------------------- core
    def _run(self, req: ResearchRequest) -> PipelineState:
        tid = new_trace_id()
        try:
            return self.pipeline.run(req, tid)
        except Exception as e:  # noqa: BLE001 - last line of defence; the failure is reported, never hidden
            log.exception("unexpected pipeline error")
            st = PipelineState(trace_id=tid, request=req, today=self.today, status=Status.ERROR)
            st.add(F.INTERNAL_ERROR, f"({e.__class__.__name__})")
            return st

    def _research_payload(self, st: PipelineState) -> dict:
        return dict(trace_id=st.trace_id, status=st.status, request=st.request, question_analysis=st.qa,
                    candidate_sources=st.candidates, evidence=st.evidence, version_notes=st.version_notes,
                    conflicts=st.conflicts, missing_facts=st.missing_facts, limitations=st.limitations,
                    confidence=st.confidence, steps=st.steps, system=self.system_info())

    def research(self, req: ResearchRequest) -> ResearchResponse:
        st = self._run(req)
        resp = ResearchResponse(**self._research_payload(st))
        self._trace("research", resp)
        return resp

    def analyze(self, req: ResearchRequest) -> AnalyzeResponse:
        st = self._run(req)
        if st.qa is None:  # internal error before question analysis
            from .models import QuestionAnalysis
            st.qa = QuestionAnalysis(raw=req.question, valid=False)
        analysis = self._safe_analysis(st)
        payload = self._research_payload(st)  # after analysis: model failure may add a limitation
        resp = AnalyzeResponse(**payload, answer_summary=self._summary(st, analysis), analysis=analysis)
        self._trace("analyze", resp)
        return resp

    def _safe_analysis(self, st: PipelineState) -> LegalAnalysis:
        try:
            return self.analyzer.analyze(st, self.corpus)
        except Exception:  # noqa: BLE001
            log.exception("analyzer crashed; using extractive fallback")
            st.add(F.MODEL_FAILURE, "(analyzer error)")
            a = ExtractiveAnalyzer().analyze(st, self.corpus)
            a.generated_by = "extractive_fallback"
            return a

    @staticmethod
    def _summary(st: PipelineState, a: LegalAnalysis) -> str:
        if not st.evidence:
            block = next((l for l in st.limitations if l.severity == "blocking"), None)
            return ("No evidence-backed answer could be established. " + (block.message if block else "")
                    + f" Status: {st.status.value}.").strip()
        order = {"VERIFIED": 0, "INTERPRETATION": 1, "SOURCE_DERIVED": 2}   # current, verbatim text first
        facts = sorted((s for s in a.analysis if s.label.value in order), key=lambda s: order[s.label.value])[:3]
        body = " | ".join(f"{s.text} {s.evidence_ids}" for s in facts) or "Evidence found but no statement could be made."
        return f"{body} (confidence: {st.confidence}; status: {st.status.value}; see limitations)"

    def _trace(self, endpoint: str, resp: ResearchResponse) -> None:
        d = self.settings.trace_dir
        if not d:
            return
        try:
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "traces.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"endpoint": endpoint, **json.loads(resp.model_dump_json())}) + "\n")
        except OSError as e:
            log.warning("could not write trace: %s", e)


def build_service(settings: Settings | None = None) -> LegalIntelligenceService:
    return LegalIntelligenceService(settings or Settings.from_env())

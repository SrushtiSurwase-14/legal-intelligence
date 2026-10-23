"""HTTP API: POST /research, POST /analyze, GET /health."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings
from .logging_config import new_trace_id
from .models import AnalyzeResponse, ResearchRequest, ResearchResponse
from .service import LegalIntelligenceService

log = logging.getLogger("li.api")


def create_app(settings: Settings | None = None, service: LegalIntelligenceService | None = None) -> FastAPI:
    app = FastAPI(title="Legal Intelligence Backend", version=__version__,
                  description="Evidence-first legal research. Informational only - not legal advice.")
    startup_error: str | None = None
    svc = service
    if svc is None:
        try:
            svc = LegalIntelligenceService(settings or Settings.from_env())
        except Exception as e:  # noqa: BLE001 - reported by /health instead of crashing at import
            startup_error = f"{e.__class__.__name__}: {e}"
            log.exception("service failed to start")

    def _unavailable() -> JSONResponse:
        detail = startup_error or "; ".join(svc.corpus.load_errors) if svc else startup_error
        return JSONResponse(status_code=503, content={
            "status": "error", "trace_id": new_trace_id(),
            "message": "Service not ready: no documents are loaded.", "detail": detail})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):  # noqa: ARG001
        tid = new_trace_id()
        log.exception("unhandled error trace_id=%s", tid)
        return JSONResponse(status_code=500, content={
            "status": "error", "trace_id": tid, "message": "Unexpected internal error. No answer was produced.",
            "limitations": [{"code": "INTERNAL_ERROR", "severity": "blocking",
                             "message": "Unexpected internal error."}]})

    @app.get("/health")
    def health():
        if svc is None:
            return JSONResponse(status_code=503, content={"status": "error", "version": __version__,
                                                          "problems": [startup_error]})
        h = svc.health()
        return JSONResponse(status_code=200 if h["status"] == "ok" else 503, content=h)

    @app.post("/research", response_model=ResearchResponse)
    def research(req: ResearchRequest):
        if svc is None or not svc.ready:
            return _unavailable()
        return svc.research(req)

    @app.post("/analyze", response_model=AnalyzeResponse)
    def analyze(req: ResearchRequest):
        if svc is None or not svc.ready:
            return _unavailable()
        return svc.analyze(req)

    return app

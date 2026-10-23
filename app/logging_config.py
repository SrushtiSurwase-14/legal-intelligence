"""Logging with a per-request trace id so every log line can be tied to one API response."""
from __future__ import annotations

import contextvars
import logging
import uuid

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def set_trace_id(tid: str):
    return _trace_id.set(tid)


def reset_trace_id(token) -> None:
    _trace_id.reset(token)


class _TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id.get()
        return True


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger("li")
    if getattr(root, "_li_configured", False):
        root.setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(trace_id)s] %(name)s: %(message)s"))
    handler.addFilter(_TraceFilter())
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    root._li_configured = True  # type: ignore[attr-defined]

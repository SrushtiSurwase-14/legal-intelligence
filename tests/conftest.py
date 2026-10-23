import json
import logging
from datetime import date
from pathlib import Path

import pytest

from app.config import ROOT, Settings
from app.service import LegalIntelligenceService

TODAY = date(2026, 10, 22)
logging.getLogger("li").setLevel(logging.ERROR)


def make_settings(**kw) -> Settings:
    base = dict(today=TODAY, trace_dir=None, log_level="ERROR")
    base.update(kw)
    return Settings.from_env(**base)


@pytest.fixture(scope="session")
def service() -> LegalIntelligenceService:
    return LegalIntelligenceService(make_settings())


@pytest.fixture()
def fresh_service():
    """Factory for services with custom settings (failure simulation, llm mode, ...)."""
    def _make(**kw):
        return LegalIntelligenceService(make_settings(**kw))
    return _make


def write_doc(dirpath: Path, doc_id: str, text: str, **meta):
    base = dict(doc_id=doc_id, title=f"Doc {doc_id}", jurisdiction="Freedonia", issuing_authority="Test",
                document_type="act", publication_date="2020-01-01", effective_date="2020-01-01",
                amendment_status="original", source_url=f"synthetic://{doc_id}", version="v1",
                retrieval_date="2026-10-22", role="primary", relations=[], is_synthetic=True,
                file=f"{doc_id}.txt")
    base.update(meta)
    (dirpath / f"{doc_id}.txt").write_text(text, encoding="utf-8")
    (dirpath / f"{doc_id}.meta.json").write_text(json.dumps(base), encoding="utf-8")


@pytest.fixture()
def tmp_corpus(tmp_path):
    (tmp_path / "jurisdictions.json").write_text(json.dumps(
        {"Freedonia": {"parent": None, "aliases": ["freedonia"]}}), encoding="utf-8")
    write_doc(tmp_path, "d1", "Section 1. Hours. No employee shall work more than 8 hours in a day.\n\n"
                              "Section 2. Rest. Every employee gets one rest day weekly.")
    return tmp_path

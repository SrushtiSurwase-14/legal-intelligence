"""Validate data/corpus (or another folder): metadata schema, relations, status consistency, chunking.

    python scripts/validate_corpus.py [path]
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.ingestion import Corpus  # noqa: E402

path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "corpus"
c = Corpus(path)
print(f"documents: {len(c.sources)}  chunks: {len(c.chunks)}  fingerprint: {c.fingerprint()}")
print("roles:", dict(Counter(s.role.value for s in c.sources.values())))
print("synthetic:", sum(s.is_synthetic for s in c.sources.values()), "| real:", sum(not s.is_synthetic for s in c.sources.values()))
for e in c.load_errors:
    print("ERROR  ", e)
for w in c.warnings:
    print("WARNING", w)
no_sections = [d for d in c.sources if not any(ch.section_id for ch in c.chunks if ch.doc_id == d)]
if no_sections:
    print("NOTE   documents without 'Section N.' headings (paragraph chunking used):", no_sections)
sys.exit(1 if c.load_errors else 0)

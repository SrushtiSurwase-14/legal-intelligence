"""Scaffold a metadata file for a document you added.

    python scripts/new_source.py data/corpus/my_act.txt
Creates my_act.meta.json with TODO placeholders. validate_corpus.py fails until you fill them in
(the dates must be real dates - this is deliberate, so nothing is guessed).
"""
import json
import sys
from pathlib import Path

txt = Path(sys.argv[1])
meta = txt.with_suffix(".meta.json")
if meta.exists():
    sys.exit(f"{meta} already exists")
meta.write_text(json.dumps({
    "doc_id": txt.stem, "title": "TODO official title", "jurisdiction": "TODO must match jurisdictions.json",
    "issuing_authority": "TODO", "document_type": "TODO act|rules|notification|order|circular|policy|judgment|commentary",
    "publication_date": "TODO YYYY-MM-DD", "effective_date": "TODO YYYY-MM-DD or null",
    "amendment_status": "unknown", "source_url": "TODO official URL you actually downloaded it from",
    "version": "TODO e.g. gazette date or consolidated-to date", "retrieval_date": "TODO YYYY-MM-DD you downloaded it",
    "role": "primary", "relations": [], "is_synthetic": False, "file": txt.name, "notes": ""}, indent=2))
print("created", meta)

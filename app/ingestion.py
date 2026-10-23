"""Document ingestion: load documents + metadata, validate, chunk, fingerprint."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from .jurisdiction import JurisdictionTree
from .models import Chunk, Relation, Source
from .textutil import sentence_spans

log = logging.getLogger("li.ingestion")

SECTION_RE = re.compile(r"^Section\s+(\d+[A-Za-z]?)\.\s", re.M)


def _split_long(text: str, max_chars: int) -> list[tuple[int, int]]:
    out, cs, ce = [], None, None
    for s, e in sentence_spans(text):
        if cs is None:
            cs, ce = s, e
        elif e - cs <= max_chars:
            ce = e
        else:
            out.append((cs, ce))
            cs, ce = s, e
    if cs is not None:
        out.append((cs, ce))
    return out or [(0, len(text))]


def chunk_text(doc_id: str, text: str, max_chars: int = 900) -> list[Chunk]:
    """Split on 'Section N.' headings (legal structure); otherwise on paragraphs.

    Every chunk keeps character offsets into the original text so evidence can be re-verified.
    """
    regions: list[tuple[str, str | None, str, int, int]] = []  # label, section_id, slug, start, end
    ms = list(SECTION_RE.finditer(text))
    if ms:
        if text[: ms[0].start()].strip():
            regions.append(("Preamble", None, "pre", 0, ms[0].start()))
        for i, m in enumerate(ms):
            end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
            regions.append((f"Section {m.group(1)}", m.group(1), f"s{m.group(1).lower()}", m.start(), end))
    else:
        for i, m in enumerate(re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", text), 1):
            regions.append((f"Paragraph {i}", None, f"p{i}", m.start(), m.end()))

    chunks: list[Chunk] = []
    for label, sid, slug, start, end in regions:
        seg = text[start:end]
        start += len(seg) - len(seg.lstrip())
        seg = text[start:end].rstrip()
        end = start + len(seg)
        if not seg:
            continue
        parts = _split_long(seg, max_chars) if len(seg) > max_chars else [(0, len(seg))]
        for n, (ps, pe) in enumerate(parts, 1):
            cid = f"{doc_id}#{slug}" + (f"-{n}" if len(parts) > 1 else "")
            chunks.append(Chunk(chunk_id=cid, doc_id=doc_id, section=label, section_id=sid,
                                text=seg[ps:pe], start=start + ps, end=start + pe))
    return chunks


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Corpus:
    """In-memory view of data/corpus. Load problems are recorded, never swallowed."""

    def __init__(self, corpus_dir: Path):
        self.dir = Path(corpus_dir)
        self.sources: dict[str, Source] = {}
        self.texts: dict[str, str] = {}
        self.paths: dict[str, Path] = {}
        self.hashes: dict[str, str] = {}
        self.chunks: list[Chunk] = []
        self.load_errors: list[str] = []
        self.warnings: list[str] = []
        self.simulate_unavailable = False
        self.tree = JurisdictionTree.load(self.dir / "jurisdictions.json")
        self._load()
        self._check_consistency()

    # ---- loading
    def _load(self) -> None:
        if not self.dir.exists():
            self.load_errors.append(f"corpus directory not found: {self.dir}")
            return
        for meta_path in sorted(self.dir.rglob("*.meta.json")):
            try:
                src = Source.model_validate(json.loads(meta_path.read_text(encoding="utf-8")))
                if src.doc_id in self.sources:
                    raise ValueError(f"duplicate doc_id {src.doc_id}")
                txt_path = meta_path.parent / src.file
                text = txt_path.read_text(encoding="utf-8")
            except Exception as e:  # noqa: BLE001 - recorded and surfaced via /health
                msg = f"{meta_path.name}: {str(e)[:300]}"
                self.load_errors.append(msg)
                log.error("failed to load %s", msg)
                continue
            self.sources[src.doc_id] = src
            self.texts[src.doc_id] = text
            self.paths[src.doc_id] = txt_path
            self.hashes[src.doc_id] = _sha(text)
            self.chunks.extend(chunk_text(src.doc_id, text))
        log.info("loaded %d documents, %d chunks, %d errors", len(self.sources), len(self.chunks),
                 len(self.load_errors))

    def _check_consistency(self) -> None:
        for s in self.sources.values():
            if self.tree.names and s.jurisdiction not in self.tree.nodes:
                self.warnings.append(f"{s.doc_id}: jurisdiction '{s.jurisdiction}' not in jurisdictions.json")
            for r in s.relations:
                t = self.sources.get(r.target)
                if t is None:
                    self.warnings.append(f"{s.doc_id}: relation target '{r.target}' not in corpus")
                    continue
                if r.type == "amends" and t.amendment_status not in ("amended", "superseded"):
                    self.warnings.append(f"{r.target}: amended by {s.doc_id} but amendment_status is "
                                         f"'{t.amendment_status}'")
                if r.type == "supersedes" and t.amendment_status != "superseded":
                    self.warnings.append(f"{r.target}: superseded by {s.doc_id} but amendment_status is "
                                         f"'{t.amendment_status}'")

    # ---- queries
    def incoming(self, doc_id: str) -> list[tuple[Source, Relation]]:
        """Relations from other documents that point at doc_id."""
        return [(s, r) for s in self.sources.values() for r in s.relations if r.target == doc_id]

    def related_doc_ids(self, doc_id: str) -> set[str]:
        out = {r.target for r in self.sources[doc_id].relations if r.target in self.sources}
        out |= {s.doc_id for s, _ in self.incoming(doc_id)}
        return out

    def read_text(self, doc_id: str) -> str:
        """Re-read the document from disk (used to verify evidence against the live source)."""
        return self.paths[doc_id].read_text(encoding="utf-8")

    def verify_available(self, doc_id: str) -> tuple[bool, str]:
        if self.simulate_unavailable:
            return False, "simulated source outage"
        try:
            text = self.read_text(doc_id)
        except OSError as e:
            return False, f"source file cannot be read ({e.__class__.__name__})"
        if _sha(text) != self.hashes[doc_id]:
            return False, "source file changed since indexing; re-start the service to re-index"
        return True, "ok"

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for d in sorted(self.hashes):
            h.update(f"{d}:{self.hashes[d]}".encode())
        return h.hexdigest()[:16]

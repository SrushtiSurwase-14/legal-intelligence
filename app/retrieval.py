"""Retrieval: BM25 (pure Python, deterministic) + an optional, experimental embedding reranker."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from .ingestion import Corpus
from .models import Chunk
from .textutil import index_stems, query_terms


class RetrievalError(RuntimeError):
    pass


@dataclass
class Hit:
    chunk: Chunk
    score: float
    coverage: float                    # share of distinct query terms found in the chunk (0..1)
    matched_terms: list[str] = field(default_factory=list)
    via: str = "search"                # 'search' | 'version_expansion'


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int = 5, allowed_docs: set[str] | None = None,
               exclude_terms: tuple[str, ...] | list[str] = ()) -> list[Hit]: ...


class BM25Retriever:
    name = "bm25"

    def __init__(self, corpus: Corpus, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.entries: list[tuple[Chunk, Counter, int]] = []
        for c in corpus.chunks:
            if c.section == "Preamble":  # title/marker block only; the title is indexed with every chunk anyway
                continue
            title = corpus.sources[c.doc_id].title
            toks = index_stems(f"{title} {c.section} {c.text}")  # title is indexed with every chunk
            self.entries.append((c, Counter(toks), len(toks)))
        n = len(self.entries)
        self.avgdl = (sum(dl for *_, dl in self.entries) / n) if n else 0.0
        df: Counter = Counter()
        for _, tf, _ in self.entries:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query, k=5, allowed_docs=None, exclude_terms=()):
        q = query_terms(query, exclude_terms)
        if not q or not self.entries:
            return []
        hits: list[Hit] = []
        for chunk, tf, dl in self.entries:
            if allowed_docs is not None and chunk.doc_id not in allowed_docs:
                continue
            score, matched = 0.0, []
            for t in q:
                f = tf.get(t, 0)
                if f:
                    score += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                    matched.append(t)
            if matched:
                hits.append(Hit(chunk, round(score, 4), round(len(matched) / len(q), 4), matched))
        hits.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
        return hits[:k]


class FailingRetriever:
    """Used to demonstrate a failed dependency (Test E)."""
    name = "failing"

    def search(self, *a, **kw):
        raise RetrievalError("simulated retriever outage")


class HybridRetriever:
    """EXPERIMENTAL. BM25 candidates reranked by sentence-embedding similarity.

    Embeddings only reorder chunks that already matched lexically, so they cannot invent a match.
    Requires `pip install sentence-transformers` and a model download. Not exercised in the
    offline test run (see tests/test_hybrid_optional.py, skipped when the package is missing).
    """
    name = "hybrid-bm25+embedding"

    def __init__(self, corpus: Corpus, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer  # ImportError if not installed

        self.bm25 = BM25Retriever(corpus)
        self.model = SentenceTransformer(model_name)
        self.index = {c.chunk_id: i for i, c in enumerate(corpus.chunks)}  # all chunks embedded; BM25 gates
        self.emb = self.model.encode([c.text for c in corpus.chunks], normalize_embeddings=True)

    def search(self, query, k=5, allowed_docs=None, exclude_terms=()):
        cand = self.bm25.search(query, k=k * 4, allowed_docs=allowed_docs, exclude_terms=exclude_terms)
        if not cand:
            return []
        qv = self.model.encode([query], normalize_embeddings=True)[0]
        cand.sort(key=lambda h: -float(self.emb[self.index[h.chunk.chunk_id]] @ qv))
        return cand[:k]


def build_retriever(corpus: Corpus, kind: str = "bm25", simulate_failure: str | None = None) -> Retriever:
    if simulate_failure == "retriever":
        return FailingRetriever()
    if kind == "hybrid":
        return HybridRetriever(corpus)
    return BM25Retriever(corpus)

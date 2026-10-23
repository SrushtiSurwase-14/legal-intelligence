import pytest

pytest.importorskip("sentence_transformers")  # SKIPPED unless installed (experimental feature)


def test_hybrid_retriever_returns_same_candidates_as_bm25():
    from app.config import ROOT
    from app.ingestion import Corpus
    from app.retrieval import BM25Retriever, HybridRetriever
    c = Corpus(ROOT / "data" / "corpus")
    q = "daily hours of work"
    assert {h.chunk.chunk_id for h in HybridRetriever(c).search(q, k=3)} <= \
           {h.chunk.chunk_id for h in BM25Retriever(c).search(q, k=12)}

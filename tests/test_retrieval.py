import pytest

from app.config import ROOT
from app.ingestion import Corpus
from app.retrieval import BM25Retriever, FailingRetriever, RetrievalError


@pytest.fixture(scope="module")
def corpus():
    return Corpus(ROOT / "data" / "corpus")


def test_bm25_ranks_relevant_section_first(corpus):
    r = BM25Retriever(corpus)
    hits = r.search("weekly rest day for employees", k=3)
    assert hits[0].chunk.chunk_id == "act_2010#s5"


def test_bm25_is_deterministic(corpus):
    r = BM25Retriever(corpus)
    a = [(h.chunk.chunk_id, h.score) for h in r.search("daily hours of work", k=5)]
    b = [(h.chunk.chunk_id, h.score) for h in BM25Retriever(corpus).search("daily hours of work", k=5)]
    assert a == b


def test_allowed_docs_filter(corpus):
    r = BM25Retriever(corpus)
    hits = r.search("registration of establishment", k=10, allowed_docs={"province_rules_2021"})
    assert hits and all(h.chunk.doc_id == "province_rules_2021" for h in hits)


def test_no_match_returns_empty(corpus):
    assert BM25Retriever(corpus).search("quantum entanglement experiments") == []


def test_failing_retriever_raises():
    with pytest.raises(RetrievalError):
        FailingRetriever().search("anything")

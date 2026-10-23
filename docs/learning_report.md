# Learning Report — Legal Intelligence Backend Foundation

## What I knew before (Day 0)
- **Python / FastAPI / pytest:** Familiar with basic Python and REST API development, but had limited exposure to building strictly bounded, evidence-first retrieval pipelines.
- **RAG / Embeddings / LLM experience:** Knew general concepts of LLMs and basic chatbots, but had not worked with hallucination guards, coverage gating, or deterministic legal-retrieval architectures.
- **Legal-domain knowledge:** Understood basic concepts of statutes and regulations, but did not have practical experience modelling legal versioning, statutory amendments, or conflicting jurisdictions.

## What I learned
- **RAG & Retrieval:** Learned why BM25 with query coverage gating (`LI_MIN_COVERAGE = 0.30`) is safer than unconstrained vector search in high-stakes domains like law. Low coverage stops poor retrieval from fabricating answers.
- **Legal Versioning:** Understood the distinction between publication date, effective date, and as-of date. Learned how relationships (`amends`, `supersedes`, `clarifies`) must be exposed rather than silently selecting the newest document.
- **Hallucination Control:** Learned how the system prevents hallucination by extracting verbatim quotes with character offsets (`char_start`, `char_end`) and re-verifying them against live text files on disk.
- **Testing Discipline:** Learned the importance of negative and failure testing (`test_failures.py`). A happy-path test only shows what works, but failure tests prove that the system gracefully handles unanswerable questions, missing facts, and broken dependencies.
- **Engineering Reproducibility:** Learned the value of determinism—pinning `LI_TODAY` and tracking corpus fingerprints ensures identical inputs always produce identical, audit-proof outputs.

## What I built / verified
- Successfully set up and ran the entire backend service (`uvicorn app.main:app`).
- Verified all 122 automated unit and integration tests across all modules.
- Executed and validated all 19 evaluation questions (`evaluation/run_eval.py`), achieving a 100% pass rate (19/19).
- Tested the interactive API endpoints (`/health`, `/research`, `/analyze`) via FastAPI's Swagger UI.
- Verified all 10 required failure modes and dependency failure scenarios (Test E).

## What I could not solve (Current Limitations)
- **Lexical Stemmer Limits:** Pure BM25 with custom stemming can struggle with complex legal synonyms (e.g., "sacked" vs. "terminated").
- **Automatic Amendment Parsing:** Version relations (`amends`, `supersedes`) currently rely on structured metadata rather than being parsed automatically from raw gazette text.
- **Complex Conflict Classification:** The rule-based conflict detector currently flags numeric conflicts for specific units (hours, days, persons) between unrelated primary acts, but cannot interpret legal precedence between federal and provincial laws (it deliberately leaves this to human legal review).

## What I would do next
1. Introduce semantic reranking using the hybrid retriever (`sentence-transformers`) once evaluated on a larger labelled test set.
2. Build an NLP-based amendment extraction step to automatically detect "Section X is hereby substituted" patterns.
3. Add JWT authentication and rate limiting for multi-tenant deployment.

## How I verified my work
- Run `python -m pytest` → 122 passed, 1 skipped.
- Run `python evaluation/run_eval.py` → 19/19 passed.
- Started server via `uvicorn app.main:app --reload` and tested live requests on `http://127.0.0.1:8000/docs`.
- Verified clean dependency installation on a fresh virtual environment.

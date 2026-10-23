# System Understanding Note

> The brief said an existing codebase would be provided; none was. This note describes the **baseline built from scratch** for this
> submission. Verify every statement yourself by running the commands (the candidate must be able to explain this without notes).

## 1. What the system is
A FastAPI service that answers legal/policy research questions **only from a controlled set of documents**, returns verbatim
evidence, exposes document versions/relationships, and refuses to conclude without evidence.

## 2. Architecture and execution flow
See `docs/architecture.png`. Request path: `app/api.py` -> `app/service.py` -> `app/pipeline.py` (6 steps) -> `app/analysis.py`.
Each step is recorded in the response `steps` list (status + duration), so a failure is always visible.

## 3. Component inventory
| Concern | Where |
|---|---|
| Application entry point | `app/main.py` (`uvicorn app.main:app`) |
| Backend structure | `api.py` (HTTP) / `service.py` (wiring, tracing) / `pipeline.py` (research) / `analysis.py` (reasoning output) |
| AI/model component | `llm.py` + `analysis.py::LLMAnalyzer` (optional, guarded); default analyzer is rule-based |
| Retrieval component | `retrieval.py` (BM25; experimental hybrid) |
| Data sources | `data/corpus/*.txt` + `*.meta.json` + `jurisdictions.json` (fictional sample) |
| Configuration | `config.py`, `.env.example` |
| APIs | `GET /health`, `POST /research`, `POST /analyze` |
| Tests | `tests/` (123) and `evaluation/` (19 questions) |
| Documentation | `README.md`, `docs/` |
| Dependencies | `requirements.txt` (fastapi, uvicorn, pydantic, python-dotenv, pytest, httpx) |

## 4. Setup instructions
See README "Quick start".

## 5. Baseline test result
Run `python -m pytest` and `python evaluation/run_eval.py`. Build-environment result: 122 passed, 1 skipped, 0 failed; 19/19
evaluation cases as expected (`docs/test_report.md`, `docs/evaluation_report.md`). **Re-run and replace with your own numbers.**

## 6. What works / what does not / what is missing / unclear / assumptions
**Works:** the full pipeline on the sample corpus; versioning; failure handling; API; reproducible clean install.
**Does not work / not done:** real-world documents (none bundled), live web search, OCR, authentication, persistence.
**Missing:** amendment extraction from text (relations are hand-entered metadata); semantic retrieval by default.
**Unclear (for you to resolve):** how the real target company expects "source discovery" (local corpus vs live web) - the code
supports local discovery only; whether provincial rules should *override* national rules (system refuses to decide).
**Assumptions:** documents are text with `Section N.` headings; metadata is correct; jurisdiction hierarchy is a tree;
a question without a date is about *today*; employee count means "persons employed".

## 7. Known limitations
See README "Known limitations".

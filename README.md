# Legal Intelligence Backend (Task 1 submission)

An **evidence-first legal research service**. You ask a question; it finds the relevant provisions in a set of
documents, quotes them verbatim, shows how the documents relate (amended / replaced / clarified), says what is
clear and unclear, and **refuses to conclude when the evidence does not support a conclusion**.

> **Read this first - honesty notes**
> 1. The brief said an existing codebase would be provided; none was. This repository was **built from scratch** as the baseline
>    and then extended. `docs/01_system_understanding.md` documents *this* baseline.
> 2. The bundled corpus (`data/corpus`, jurisdiction "Freedonia") is **fictional**, marked `is_synthetic: true`, and every file
>    starts with a "NOT REAL LAW" banner. It exists so the system can be tested without inventing real citations.
>    **Real public documents must be added by the candidate** (see `docs/ADDING_REAL_DOCUMENTS.md`).
> 3. This project was built with an AI coding assistant (permitted by Rule 1 of the brief). The candidate must be able to explain
>    every part - see `docs/STUDY_GUIDE.md`.

## Quick start (Python 3.10+)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # optional: defaults work offline
python -m pytest                                        # expect: 122 passed, 1 skipped
python evaluation/run_eval.py                           # expect: 19/19 passed
uvicorn app.main:app --reload                           # http://127.0.0.1:8000/docs
```

Try it:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/analyze -H 'content-type: application/json' -d '{
  "question": "Do I need to register my shop with 7 employees in Northern Province?"}' | python -m json.tool
curl -s -X POST localhost:8000/analyze -H 'content-type: application/json' -d '{
  "question": "What is the maximum number of hours an employee can work in a day?",
  "jurisdiction": "Freedonia", "as_of_date": "2020-06-01"}'
```

Everything runs **offline**: retrieval is BM25 in pure Python and the default analyzer is deterministic.
No API key is needed. (An LLM mode exists - see Configuration.)

## What the system does (pipeline)

| Step | Module | What happens | Can it stop the run? |
|---|---|---|---|
| 1 Question analysis | `app/question.py` | validity, jurisdiction, as-of date, topics, facts, "predict my case" intent | yes (malformed) |
| 2 Source discovery | `app/retrieval.py` | BM25 over section-level chunks, filtered by applicable jurisdictions | yes (none found / retriever down) |
| 3 Source validation | `app/ingestion.py` | is each source still readable and unchanged since indexing? | yes (all unavailable) |
| 4 Retrieval selection | `app/pipeline.py` | quality gate (coverage + score), primary preferred over secondary | yes (poor retrieval) |
| 5 Version resolution | `app/versioning.py` | amends / supersedes / clarifies, in force on as-of date?, outdated?, conflicts | no (adds limitations) |
| 6 Evidence extraction | `app/pipeline.py` | verbatim sentence(s) + character offsets, **re-verified against the live file** | yes if nothing verifies |
| 7 Analysis | `app/analysis.py` | structured template, labelled statements, review flag, confidence | no |

`docs/architecture.png` shows the flow. `docs/failure_matrix.md` shows what happens in each failure.

### Key design decisions (be ready to defend these)
- **No evidence -> no conclusion.** Blocking limitations end the run; the analysis then contains only an explanation.
- **Every statement is labelled** `VERIFIED | SOURCE_DERIVED | INTERPRETATION | UNCERTAIN | MISSING | CONFLICTING | REQUIRES_REVIEW`.
- **Versions are exposed, never silently resolved.** Both the old and new text are returned with a status
  (`in_force`, `superseded_by_amendment`, `not_yet_in_force`, ...) relative to the as-of date.
  With no date given, the system assumes *today* and **says so** in `question_analysis.assumptions`.
- **Conflicts are shown, not resolved.** Unrelated primary provisions with different numbers for the same unit
  (e.g. 10 vs 5 persons) are flagged; hierarchy between national and provincial rules is a legal question.
- **Secondary sources are context only** unless nothing else exists (then `SECONDARY_ONLY`, confidence capped at low).
- **LLM output is never trusted.** In `llm` mode the model only writes narrative; its output must cite real evidence ids,
  contain only numbers found in the evidence, and avoid certainty words - otherwise it is discarded and the deterministic
  analysis is used (`MODEL_FAILURE`). The model is never called when there is no evidence.
- **Deterministic:** same question + same corpus + same `LI_TODAY` -> same output (tested).

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | `200 ok` or `503 degraded` (bad metadata, no documents); lists dependencies, corpus fingerprint, version |
| `POST /research` | steps 1-6: candidate sources, evidence, version notes, conflicts, limitations, confidence |
| `POST /analyze` | everything in `/research` + `answer_summary` + the structured `analysis` (Day 4 template) |

Request body (`/research`, `/analyze`):
`{"question": str (<=2000), "jurisdiction": str|null, "as_of_date": "YYYY-MM-DD"|null, "facts": {"employee_count": 12}, "top_k": 1-20|null}`

Every response has `trace_id`, `status` (`answered | partial | insufficient_evidence | malformed_question | error`),
`request`, `question_analysis`, `candidate_sources` (with full source/version metadata), `evidence`, `version_notes`,
`conflicts`, `missing_facts`, `limitations` (code, severity, message, next_step), `confidence`, `steps` (per-step status
and timing) and `system` (app version, analyzer mode, retriever, corpus fingerprint, "today"). HTTP: `422` schema errors,
`503` service not ready, `500` unexpected error (body still has a `trace_id`; no internals leaked).
A "no answer" is a **normal 200** with `status != answered` - not an error.

## Configuration (`.env`, see `.env.example`)

| Variable | Default | Meaning |
|---|---|---|
| `LI_CORPUS_DIR` | `data/corpus` | folder of `*.txt` + `*.meta.json` (+ `jurisdictions.json`) |
| `LI_ANALYZER_MODE` | `extractive` | `llm` enables the guarded LLM narrative |
| `LI_LLM_PROVIDER` / `ANTHROPIC_API_KEY` / `LI_LLM_MODEL` | `none` | needs `pip install anthropic`; **check the model name in Anthropic's docs** - the live API call was never run in the build environment |
| `LI_RETRIEVER` | `bm25` | `hybrid` = BM25 + embedding rerank (experimental, needs `sentence-transformers`) |
| `LI_MIN_COVERAGE`, `LI_MIN_SCORE`, `LI_TOP_K` | 0.30, 0.5, 5 | retrieval quality gate |
| `LI_SIMULATE_FAILURE` | empty | `retriever`, `source` or `llm` - deliberately breaks a dependency (Test E) |
| `LI_TODAY` | today | pin the date for reproducible runs |

## Adding real documents
`docs/ADDING_REAL_DOCUMENTS.md`. Short version: put `name.txt` in `data/corpus/`, run `python scripts/new_source.py data/corpus/name.txt`,
fill in the metadata (real dates, real URL), add relations for amendments, then `python scripts/validate_corpus.py`.

## Testing and evaluation
- `python -m pytest` - 123 tests (122 pass, 1 skipped: optional embedding retriever). `python scripts/make_test_report.py` regenerates `docs/test_report.md`.
- `python evaluation/run_eval.py --reports` - runs 19 questions (`evaluation/questions.json`) and regenerates `docs/evaluation_report.md` and `docs/evidence_report.md`.
- Tests map to the brief: version model (`test_source_version_model.py`, `test_versioning.py`), the ten failure situations
  (`test_failures.py`), scenarios A-E (`test_pipeline_scenarios.py` + evaluation), API contract (`test_api.py`),
  LLM guard (`test_analysis_and_llm_guard.py`).

## Repository map
```
app/            api.py (FastAPI) service.py (wiring) pipeline.py analysis.py versioning.py question.py
                retrieval.py ingestion.py fallbacks.py (failure policy) llm.py models.py config.py ...
data/corpus/    fictional sample documents + metadata + jurisdictions.json
evaluation/     questions.json (19) run_eval.py results.json
tests/          pytest suite
scripts/        make_test_report.py make_failure_matrix.py make_diagram.py validate_corpus.py new_source.py pdf_to_text.py
docs/           01_system_understanding.md architecture.* source_version_model.md failure_matrix.md test_report.md
                evaluation_report.md evidence_report.md learning_report.md STUDY_GUIDE.md ROADMAP.md ADDING_REAL_DOCUMENTS.md
```
![Uploading image.png…]()

## Known limitations (no inflated claims)
1. **Fictional corpus only** until real documents are added; results say nothing about real law.
2. **Lexical retrieval.** BM25 + a crude stemmer misses synonyms ("sacked" vs "terminated") and can match on generic words.
   Thresholds (`min_coverage` etc.) were tuned on 19 questions - a tiny set; expect to re-tune on real documents. One threshold
   change (0.34 -> 0.30) was made after an evaluation case (Q09) exposed a miss - that is calibration on the test set, not validation.
3. **Rule-based conflict detection** only compares integers attached to a few units (hours, days, persons, units, holidays)
   in unrelated primary documents. It will miss conflicts expressed differently and may flag false ones.
4. **Version logic depends on correct metadata** (`relations`, `effective_date`). The system does not read amendments out of text.
5. **Section parsing** expects headings like `Section 4.` at the start of a line; other formats fall back to paragraph chunks.
6. **No authentication, rate limiting, or persistence** beyond the JSONL trace file in `logs/`.
7. **LLM mode and hybrid retriever are not exercised against real services** in the automated tests.
8. **Not legal advice.** Every analysis carries a disclaimer and a `requires_professional_review` flag.

## Next steps (for the next engineer)
Add real documents and re-run the evaluation; add an amendment-extraction step; better chunking for gazette PDFs; evaluate
the hybrid retriever (recall@k on a labelled set); add auth; add live official-source fetching behind the same `Corpus` interface.

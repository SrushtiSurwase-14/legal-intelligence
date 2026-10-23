# Study guide - understand every part (the brief returns the task if you cannot explain your own implementation)

Read this with the code open. For each concept: read the section, open the file, run the example.

## 1. Concepts in plain words
- **LLM**: predicts likely text. Fluent != true. It can invent citations ("hallucination"). That is why this system retrieves evidence first and *validates* anything a model writes.
- **RAG (Retrieval-Augmented Generation)**: retrieve real passages, then answer *from them*. Here retrieval is `app/retrieval.py`; the "generation" part is optional (`app/analysis.py::LLMAnalyzer`).
- **Chunking** (`ingestion.py::chunk_text`): documents are cut into pieces. We cut on `Section N.` because that is how a legal provision is naturally bounded. Each chunk remembers its character offsets.
- **Embeddings**: text -> vector of numbers; similar meaning = nearby vectors. Used only in the optional `HybridRetriever` (reranks BM25 results). *Why not default?* It needs a model download, is non-trivial to make deterministic, and can surface "semantically similar but legally irrelevant" text. BM25 is explainable: you can print which words matched.
- **BM25** (`BM25Retriever`): scores a chunk higher when it contains rare query words, many times, in a short chunk. Formula: `idf(t) * f*(k1+1) / (f + k1*(1-b+b*len/avglen))`. Run `python -c` examples from tests/test_retrieval.py.
- **Stemming** (`textutil.stem`): "registration/registered/register" -> `regist`. Crude on purpose; limits: it can merge unrelated words and misses synonyms.
- **Coverage**: share of *distinct query terms* found in the chunk. Our quality gate: low coverage => "poor retrieval" => no conclusion.
- **Primary vs secondary source**: the law itself (Act, rules, notification, order, circular) vs commentary. Only primary text may establish what the law says.
- **Effective date vs publication date**: a notification published 15 March 2019 may take effect 1 April 2019. Which text "applies" depends on the effective date and the date the *question is about* (`as_of`).
- **Amends / supersedes / clarifies**: amends = changes parts; supersedes = replaces whole; clarifies = explains without changing. Stored as `relations` on the *newer* document (`models.Relation`).
- **Deterministic vs probabilistic**: our pipeline is deterministic (same input -> same output; tested). A model is probabilistic, so we only let it write narrative that passes checks.
- **Structured output**: Pydantic models (`models.py`) force a fixed shape; FastAPI validates requests and serialises responses from them.

## 2. Follow one request through the code (do this by hand)
`POST /analyze {"question":"Do I need to register my shop with 7 employees in Northern Province?"}`
1. `api.py::analyze` -> `service.analyze` -> `service._run` -> `pipeline.run` (assigns a `trace_id`).
2. `question.analyze_question`: valid; jurisdiction detected by alias "northern province" -> `Freedonia/Northern Province`; `employee_count=7` parsed; "my" => applicability question; as-of = today (assumed, recorded).
3. Jurisdiction filter: `tree.applicable()` = the province **and its parent Freedonia** -> allowed documents.
4. `retriever.search`: BM25 hits; `source_validation`: file readable + SHA-256 unchanged.
5. Quality gate: coverage >= 0.30, score >= 0.5, relative cut-offs; primary preferred.
6. `versioning`: relations -> notes; `provision_status` per chunk; `detect_conflicts` finds `persons: {10}` vs `{5}` between unrelated primary documents -> `CONFLICTING_SOURCES`.
7. `_extract_evidence`: best sentence(s) per chunk; offsets; **re-read file and compare** (`verified`).
8. `finalise`: status `partial`, confidence `low` (conflict = +3 points).
9. `analysis.ExtractiveAnalyzer`: VERIFIED quotes, INTERPRETATION for the 7-vs-10 and 7-vs-5 comparisons, CONFLICTING statement, review flag.

## 3. Why each safety rule exists (tie each to a test)
| Rule | Why | Test |
|---|---|---|
| Quote re-verified against the live file | a changed/corrupted source must not produce "evidence" | `test_2c_source_modified_after_indexing_is_detected` |
| Model never called with zero evidence | otherwise it would answer from memory | `test_llm_not_called_when_there_is_no_evidence` |
| Numbers in LLM text must appear in evidence | catches invented figures | `test_invalid_llm_output...[numbers]` |
| Amendment is not a "conflict" | it is version info, shown as a relation | `test_3b_amendment_is_not_reported_as_conflict` |
| Facts missing => rule not applied | else we would guess the user's facts | `test_6_missing_facts` |
| As-of assumption is stated | silent assumptions are hidden failures | `test_no_date_assumes_today_and_says_so` |

## 4. Likely viva / interview questions - practise answering aloud
1. Draw the pipeline and say what each step can fail with. (see `docs/architecture.png`, `failure_matrix.md`)
2. Why BM25 and not embeddings first? When would embeddings help? How would you evaluate that? (recall@k on labelled questions)
3. How do you stop hallucination? (retrieve first; verbatim verification; guarded LLM; refusal path)
4. What happens if the retriever is down? (status `error`, step `source_discovery` failed, no answer) Show the test.
5. How does the system know which version applies? (`as_of`, `effective_state`, `provision_status`) Walk through Q01 vs Q05.
6. What if no date is given? (assume today, state it)  What if only a year is given and the amendment is in that year? (`uncertain_timing`)
7. Why is the Northern Province case "conflicting" and the 2019 notification not? (relations)
8. What does `confidence` mean here? How computed? Is it a probability? (No - rule-based points; document that.)
9. What are the weaknesses of your conflict detector? (integers+units only; false positives/negatives)
10. Why did you change `min_coverage` from 0.34 to 0.30? Is that valid evidence of quality? (tuning on test set - weak)
11. What does `requires_professional_review` do and when is it true?
12. How would you add a new jurisdiction / a new document / a new failure code? (jurisdictions.json; meta.json; `FailureCode` + `POLICY` + regenerate matrix)
13. What would you do with 50,000 documents? (vector DB / ANN index, persistent index, incremental ingestion, caching, background indexing)
14. What is not tested? (see README limitations) Be upfront.
15. Why 200 OK for "no answer" rather than 404/500? (not a transport error; a legitimate, explained result)
16. How is the build reproducible? (pinned `LI_TODAY`, corpus fingerprint, deterministic retrieval, `requirements.txt`)

## 5. Exercises to make it yours (do at least three before submitting)
- Add a new fictional section and a question about it; watch retrieval and tests.
- Break `effective_date` of the 2019 notification to 2021; predict, then run Q01.
- Change `min_coverage` to 0.5 and see which evaluation cases flip. Explain why.
- Add a `LI_TOP_K=1` run and explain what is lost.
- Write a new failure case (e.g. two amendments to the same section) and a test for it.

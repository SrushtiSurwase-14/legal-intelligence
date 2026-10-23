# 7-day roadmap (adapted: the codebase was not provided, so Day 1 documents the baseline built from scratch)

Mark each item done only when **you** ran it. "Mine" = you must do/understand it personally.

| Day | Brief's mission | What already exists in this repo | **Your job (mine)** |
|---|---|---|---|
| 1 Understand | system understanding note | `docs/01_system_understanding.md`, `docs/architecture.png`, runnable baseline, `pytest` result | Install, run, **read every file in `app/`** in the order of `STUDY_GUIDE.md` sec. 2; correct the note where it differs from what you see; add your own "unclear" list; write 5 min spoken explanation |
| 2 Research pipeline | question -> evidence | `pipeline.py` steps 1-6, evidence + citations, primary/secondary | **Download 6-10 REAL public documents** (guide: `ADDING_REAL_DOCUMENTS.md`); write 5 real test questions (policy, regulatory, government-document, applicability, historical) |
| 3 Version model | source & version info | `models.Source`, `versioning.py`, tests | Encode a **real** amended-document pair with `relations`; run `validate_corpus.py`; add tests for it |
| 4 Legal reasoning | structured analysis | `analysis.py`, template fields | Read 5 outputs critically; find one statement you would not trust; fix wording/logic |
| 5 Failure & safety | 10 failure cases | `fallbacks.py`, `test_failures.py`, `failure_matrix.md` | Invent 2 new failure cases; add policy + tests |
| 6 API & repro | /research /analyze /health | `api.py`, `test_api.py`, clean-venv run | Follow README on a **fresh folder / second machine**; fix what is unclear |
| 7 Demo | tests A-E | `evaluation/`, `evidence_report.md` | Re-run on real docs; regenerate reports; record screen demo; fill `learning_report.md` honestly |

## Checklist against the acceptance gates
- [ ] G1 I can explain the system without opening code
- [ ] G2 `pytest` passes on a clean clone (run it)
- [ ] G3 research pipeline works on **real** documents
- [ ] G4 evidence preserved (quotes + offsets + verified flag)
- [ ] G5 source/version metadata captured for real documents
- [ ] G6 structured analysis fields all present
- [ ] G7 failures visible (limitations + steps)
- [ ] G8 automated tests exist and are executable
- [ ] G9 API usable (`/docs`)
- [ ] G10 README lets another person continue

## Submission package (map to the brief)
A repository -> this folder. B architecture -> `docs/architecture.png`. C test report -> `docs/test_report.md` (regenerate).
D evaluation dataset -> `evaluation/questions.json` (extend with real-document questions). E evidence report -> `docs/evidence_report.md` (regenerate after real docs).
F learning report -> `docs/learning_report.md` (**write yourself**). G handover README -> `README.md` (update for your real corpus).

## Things that would cause a return - double-check
Fabricated citations (never type law from memory) - results not reproducible - claiming tests you did not run - README not matching behaviour (update README numbers after you change anything) - not being able to explain a function.

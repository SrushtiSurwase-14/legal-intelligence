# Source & version model (Day 3)

Defined in `app/models.py::Source` (strict: unknown fields are rejected) and validated at load time by `app/ingestion.py::Corpus`.

| Field | Meaning |
|---|---|
| `doc_id` | unique id used in relations and evidence |
| `title`, `document_type` | e.g. act, rules, notification, order, circular, commentary |
| `jurisdiction`, `issuing_authority` | must exist in `jurisdictions.json`; hierarchy via `parent` |
| `publication_date` / `effective_date` | issued vs in force (can differ; effective may be null for commentary) |
| `amendment_status` | `original / amended / superseded / amending_instrument / clarifying_instrument / not_applicable / unknown` |
| `source_url`, `version`, `retrieval_date` | where, which version, when it was fetched |
| `role` | `primary` (the law) or `secondary` (commentary) |
| `relations[]` | on the *newer* document: `amends | supersedes | clarifies | describes` + `target` + `affected_sections` |

Consistency checks (warnings, shown by `/health`): relation targets exist; target of `amends` is marked `amended`/`superseded`;
target of `supersedes` is `superseded`.

## How time is handled
`as_of` = request date, else a full date in the question, else a year ("in 2015"), else **today (assumed and stated)**.
`versioning.effective_state` compares an instrument's effective date with `as_of` -> `effective | not_yet | ambiguous (same year) | unknown`.
`versioning.provision_status` then labels each retrieved provision: `in_force`, `superseded_by_amendment`, `superseded`,
`not_yet_in_force`, `uncertain_timing`, `superseded_replacement_unknown`.

## Worked example (sample corpus)
Act 2010 s4: 9 hours. Notification 2019 (effective 2019-04-01) substitutes s4: 8 hours.
- as of 2020 -> Act s4 `superseded_by_amendment`, Notification `in_force` (answer: 8 hours; both shown, linked by an `amends` note)
- as of 2015 -> Act s4 `in_force`, Notification `not_yet_in_force` (answer: 9 hours)
- "in 2019" -> `uncertain_timing` (needs the exact date)
Tests: `tests/test_versioning.py`, `tests/test_source_version_model.py`.

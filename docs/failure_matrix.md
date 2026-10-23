# Failure & safety matrix

*Generated from `app/fallbacks.py` by `scripts/make_failure_matrix.py` - do not edit by hand.*

Principle: **no evidence -> no fabricated conclusion -> explain limitation -> ask for missing information -> escalate when required.**

| Code | Situation | Severity | What the system does | Escalate? |
|---|---|---|---|---|
| `NO_SOURCE_FOUND` | No source found | blocking | Stop. No evidence, no conclusion. Report that nothing relevant exists in the document set. | yes |
| `SOURCE_UNAVAILABLE` | Source unavailable | warning | Drop the unreadable/changed source, keep evidence from the rest, and say which source was lost. If nothing is left, stop with no conclusion. | no |
| `CONFLICTING_SOURCES` | Conflicting sources | warning | Show both provisions side by side, do not pick a winner, lower confidence, require review. | yes |
| `POOR_RETRIEVAL` | Poor retrieval | blocking | Stop. Weak matches are listed as candidates but never used as evidence. | yes |
| `MALFORMED_QUESTION` | Malformed question | blocking | Stop before retrieval and explain what is wrong with the question. | no |
| `MISSING_FACTS` | Missing facts | warning | Answer what the evidence supports, list the missing facts, do not apply rules to unknown facts. | no |
| `MODEL_FAILURE` | Model failure | warning | Discard unusable LLM output, fall back to the deterministic extractive analysis, and say so. | no |
| `UNSUPPORTED_CONCLUSION` | Unsupported legal conclusion | warning | Show the relevant provisions but refuse to predict outcomes or declare liability. | yes |
| `OUTDATED_SOURCE` | Outdated source | warning | Flag the source as outdated; use it only for context; prefer the replacing document if present. | yes |
| `AMBIGUOUS_JURISDICTION` | Ambiguous jurisdiction | warning | Show sources from every plausible jurisdiction, flag the ambiguity, ask for the jurisdiction. If the stated jurisdiction is not covered at all, stop with no conclusion. | yes |
| `RETRIEVAL_FAILURE` | Retriever/dependency failure | blocking | Return status 'error' with the failing step visible. Never fall back to model memory. | no |
| `EVIDENCE_UNVERIFIED` | Evidence not verifiable | warning | Discard any quote that cannot be matched verbatim to the live source text. | no |
| `SECONDARY_ONLY` | Only secondary sources | warning | Show them as context, cap confidence at 'low', require review. | yes |
| `INTERNAL_ERROR` | Unexpected internal error | blocking | Return status 'error' with a trace_id; never return a partial guess. | no |

Severity meaning: `info` = shown, no effect on status; `warning` = status becomes `partial`, confidence is lowered; `blocking` = the run stops and **no conclusion is produced**.

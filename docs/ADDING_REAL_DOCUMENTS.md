# Adding real public documents (you must do this - the sample corpus is fictional)

**Goal:** 6-10 real documents on ONE topic, including at least one pair where a newer instrument amends/replaces an older one.

## Where to look (verify each site yourself; use only official/public material)
- India Code (indiacode.nic.in) - central and state Acts, consolidated text.
- eGazette of India (egazette.gov.in) and state gazettes - notifications, orders.
- Ministry / department websites (e.g. Ministry of Labour & Employment) - rules, circulars, notifications.
- Maharashtra Government Resolutions portal (gr.maharashtra.gov.in) - GRs, for a state-level topic.
Pick a topic small enough to read: e.g. *one Act + its rules + 1-2 amending notifications + 1 circular + 1 secondary explainer*.

## Steps
1. Download the document; note the **exact URL and date you downloaded it**.
2. Convert to text: copy-paste, or `python scripts/pdf_to_text.py in.pdf data/corpus/name.txt` (text PDFs only).
3. **Open the .txt and fix it by hand.** Make each provision start on a new line as `Section 4. Heading. Text...` (this is what the chunker splits on). Remove page headers/footers.
4. `python scripts/new_source.py data/corpus/name.txt` -> fill the generated `name.meta.json` (real publication/effective dates, issuing authority, version, `role` = primary for the law itself, secondary for commentary, `is_synthetic: false`).
5. Add **relations** for amendments: `{"type":"amends","target":"<doc_id of the Act>","affected_sections":["4"]}` on the *amending* document; set the amended document's `amendment_status` to `amended` (or `superseded`).
6. Add the jurisdiction(s) to `data/corpus/jurisdictions.json` (with `parent` for sub-jurisdictions).
7. `python scripts/validate_corpus.py` - fix every ERROR and WARNING.
8. Add 5+ evaluation questions about the new documents to `evaluation/questions.json`. Write the **expected behaviour first**, then run `python evaluation/run_eval.py`.
9. Decide what to do with the fictional documents: keep them for tests (the tests rely on them) - they are clearly marked. Put real documents in a separate folder and point `LI_CORPUS_DIR` at it for your real demo, or add them alongside.

## Rules
- Never type a citation from memory. Every quote must come from a file you downloaded.
- Record in your learning report what you could not parse or verify.

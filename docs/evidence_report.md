# Evidence report - integrated demonstrations (Tests A-E)

*Generated from real runs by `python evaluation/run_eval.py --reports` (today pinned to 2026-10-22).* *The corpus is fictional (Freedonia); no real law is cited.*

## Test A - straightforward (Q01)

**Question:** Under the Freedonia Shops and Establishments Act, what is the maximum number of hours an employee can be required to work in a day?  
**Request options:** jurisdiction=Freedonia, as_of_date=2020-06-01

**Expected behaviour:** Answer 8 hours from the 2019 Notification; show the original 9-hour text of Section 4 as superseded; link the two documents.

**Actual behaviour:** status `answered`, confidence `high`, professional review required: `False`.  
Answer summary: Freedonia Shops and Establishments (Amendment) Notification, 2019, Section 1 (version 2019-03-15) states: "For Section 4 of the principal Act, the following shall be substituted: No employee shall be required or allowed to work for more than 8 hours in a day." ['E2'] | Freedonia Shops and Establishments Act, 2010, Section 6 (version 2010-original) states: "An employee who works in excess of the daily limit fixed under Section 4 shall be paid for the extra hours at twice the ordinary rate of wages." ['E4'] | Freedonia Shops and Establishments Act, 2010, Section 4 (version 2010-original) reads "No employee shall be required or allowed to work for more than 9 hours in a day." - note: This text was amended by 'Freedonia Shops and Establishments (Amendment) Notification, 2019' (effective 2019-04-01); per the source metadata it is not the current text for the as-of date. The replacing text is in E2. ['E1', 'E2'] (confidence: high; status: answered; see limitations)

**Result:** PASS

**Sources:**
- `act_2010` - Freedonia Shops and Establishments Act, 2010 (primary; v2010-original; effective 2010-07-01; status amended) - *evidence*
- `notif_2019` - Freedonia Shops and Establishments (Amendment) Notification, 2019 (primary; v2019-03-15; effective 2019-04-01; status amending_instrument) - *evidence*
- `blog_2018` - Example & Partners LLP briefing: The Freedonia Shops Act explained (2018) (secondary; v2018-06-10; effective None; status not_applicable) - *candidate only (not used as evidence)*
- `circular_2023` - Circular No. 3 of 2023 - Clarification on Overtime Computation (primary; v2023-01-20; effective 2023-02-01; status clarifying_instrument) - *evidence*
- `holidays_2012` - Freedonia Public Holidays Order, 2012 (primary; v2011-12-01; effective 2012-01-01; status superseded) - *candidate only (not used as evidence)*
- `holidays_2020` - Freedonia Public Holidays Order, 2020 (primary; v2019-12-10; effective 2020-01-01; status original) - *candidate only (not used as evidence)*

**Evidence (verbatim, verified against source text):**
- [E1] `act_2010` Section 4 (superseded_by_amendment, answer): "No employee shall be required or allowed to work for more than 9 hours in a day."
- [E2] `notif_2019` Section 1 (in_force, answer): "For Section 4 of the principal Act, the following shall be substituted: No employee shall be required or allowed to work for more than 8 hours in a day."
- [E3] `circular_2023` Section 1 (not_yet_in_force, answer): "Overtime under Section 6 of the principal Act is payable for each day on which an employee works for more than 8 hours, and shall not be averaged over a week."
- [E4] `act_2010` Section 6 (in_force, answer): "An employee who works in excess of the daily limit fixed under Section 4 shall be paid for the extra hours at twice the ordinary rate of wages."
- [E5] `act_2010` Section 7 (in_force, risk): "An employer who contravenes Section 3, Section 4 or Section 6 shall be punishable with a fine not exceeding 5000 units."

**Limitations reported:**
- `OUTDATED_SOURCE` (info): A source used is outdated or superseded. 'Freedonia Shops and Establishments Act, 2010' Section 4 is shown for comparison only; its replacement is also in the evidence.

**Pipeline steps:** question_analysis:ok -> source_discovery:ok -> source_validation:ok -> retrieval_selection:ok -> version_resolution:ok -> evidence_extraction:ok

**Trace id:** `c1c3b276206749db` (changes every run).

**Known limitation of this demonstration:** runs on a small fictional corpus with lexical retrieval; see README 'Known limitations'.

## Test B - multi source conflict (Q04)

**Question:** Do I need to register my shop with 7 employees in Northern Province?

**Expected behaviour:** Show both the national (10) and provincial (5) thresholds, flag CONFLICTING_SOURCES, do NOT pick one, low confidence, review required.

**Actual behaviour:** status `partial`, confidence `low`, professional review required: `True`.  
Answer summary: Freedonia Shops and Establishments Act, 2010, Section 3 (version 2010-original) states: "Every establishment employing 10 or more persons shall be registered with the Labour Commissioner within 30 days of commencement of its business. The registration certificate shall be displayed at a prominent place in the establishment." ['E1'] | Northern Province Shops and Establishments Rules, 2021, Section 2 (version 2021-05-10) states: "In Northern Province, every establishment employing 5 or more persons shall be registered with the Provincial Labour Officer within 30 days of commencement of its business." ['E2'] | Northern Province Shops and Establishments Rules, 2021, Section 3 (version 2021-05-10) states: "Every registered establishment shall display a notice of working hours at its entrance." ['E3'] (confidence: low; status: partial; see limitations)

**Result:** PASS

**Sources:**
- `act_2010` - Freedonia Shops and Establishments Act, 2010 (primary; v2010-original; effective 2010-07-01; status amended) - *evidence*
- `province_rules_2021` - Northern Province Shops and Establishments Rules, 2021 (primary; v2021-05-10; effective 2021-06-01; status original) - *evidence*
- `blog_2018` - Example & Partners LLP briefing: The Freedonia Shops Act explained (2018) (secondary; v2018-06-10; effective None; status not_applicable) - *candidate only (not used as evidence)*
- `notif_2019` - Freedonia Shops and Establishments (Amendment) Notification, 2019 (primary; v2019-03-15; effective 2019-04-01; status amending_instrument) - *candidate only (not used as evidence)*
- `holidays_2012` - Freedonia Public Holidays Order, 2012 (primary; v2011-12-01; effective 2012-01-01; status superseded) - *candidate only (not used as evidence)*
- `holidays_2020` - Freedonia Public Holidays Order, 2020 (primary; v2019-12-10; effective 2020-01-01; status original) - *candidate only (not used as evidence)*

**Evidence (verbatim, verified against source text):**
- [E1] `act_2010` Section 3 (in_force, answer): "Every establishment employing 10 or more persons shall be registered with the Labour Commissioner within 30 days of commencement of its business. The registration certificate shall be displayed at a prominent place in the establishment."
- [E2] `province_rules_2021` Section 2 (in_force, answer): "In Northern Province, every establishment employing 5 or more persons shall be registered with the Provincial Labour Officer within 30 days of commencement of its business."
- [E3] `province_rules_2021` Section 3 (in_force, answer): "Every registered establishment shall display a notice of working hours at its entrance."
- [E4] `act_2010` Section 7 (in_force, risk): "An employer who contravenes Section 3, Section 4 or Section 6 shall be punishable with a fine not exceeding 5000 units."

**Limitations reported:**
- `CONFLICTING_SOURCES` (warning): Sources state different values and are not linked by an amendment. 1 conflict(s) found.

**Pipeline steps:** question_analysis:ok -> source_discovery:ok -> source_validation:ok -> retrieval_selection:ok -> version_resolution:ok -> evidence_extraction:ok

**Trace id:** `d400bb582c54409a` (changes every run).

**Known limitation of this demonstration:** runs on a small fictional corpus with lexical retrieval; see README 'Known limitations'.

## Test C - historical version (Q05)

**Question:** What was the daily working hour limit under the Freedonia Shops and Establishments Act in 2015?

**Expected behaviour:** Year parsed from the question; original 9-hour text is in force; the 2019 amendment is shown as NOT YET in force.

**Actual behaviour:** status `answered`, confidence `high`, professional review required: `False`.  
Answer summary: Freedonia Shops and Establishments Act, 2010, Section 6 (version 2010-original) states: "An employee who works in excess of the daily limit fixed under Section 4 shall be paid for the extra hours at twice the ordinary rate of wages." ['E1'] | Freedonia Shops and Establishments Act, 2010, Section 4 (version 2010-original) states: "No employee shall be required or allowed to work for more than 9 hours in a day." ['E2'] | Circular No. 3 of 2023 - Clarification on Overtime Computation, Section 1 (version 2023-01-20) reads "Overtime under Section 6 of the principal Act is payable for each day on which an employee works for more than 8 hours, and shall not be averaged over a week." - note: Circular No. 3 of 2023 - Clarification on Overtime Computation took effect on 2023-02-01, after the as-of date (year 2015); shown for version context only. ['E3'] (confidence: high; status: answered; see limitations)

**Result:** PASS

**Sources:**
- `act_2010` - Freedonia Shops and Establishments Act, 2010 (primary; v2010-original; effective 2010-07-01; status amended) - *evidence*
- `blog_2018` - Example & Partners LLP briefing: The Freedonia Shops Act explained (2018) (secondary; v2018-06-10; effective None; status not_applicable) - *candidate only (not used as evidence)*
- `notif_2019` - Freedonia Shops and Establishments (Amendment) Notification, 2019 (primary; v2019-03-15; effective 2019-04-01; status amending_instrument) - *version context*
- `circular_2023` - Circular No. 3 of 2023 - Clarification on Overtime Computation (primary; v2023-01-20; effective 2023-02-01; status clarifying_instrument) - *version context*
- `holidays_2012` - Freedonia Public Holidays Order, 2012 (primary; v2011-12-01; effective 2012-01-01; status superseded) - *candidate only (not used as evidence)*
- `holidays_2020` - Freedonia Public Holidays Order, 2020 (primary; v2019-12-10; effective 2020-01-01; status original) - *candidate only (not used as evidence)*

**Evidence (verbatim, verified against source text):**
- [E1] `act_2010` Section 6 (in_force, answer): "An employee who works in excess of the daily limit fixed under Section 4 shall be paid for the extra hours at twice the ordinary rate of wages."
- [E2] `act_2010` Section 4 (in_force, answer): "No employee shall be required or allowed to work for more than 9 hours in a day."
- [E3] `circular_2023` Section 1 (not_yet_in_force, version_context): "Overtime under Section 6 of the principal Act is payable for each day on which an employee works for more than 8 hours, and shall not be averaged over a week."
- [E4] `notif_2019` Section 1 (not_yet_in_force, version_context): "For Section 4 of the principal Act, the following shall be substituted: No employee shall be required or allowed to work for more than 8 hours in a day."
- [E5] `act_2010` Section 7 (in_force, risk): "An employer who contravenes Section 3, Section 4 or Section 6 shall be punishable with a fine not exceeding 5000 units."

**Limitations reported:**
- none

**Pipeline steps:** question_analysis:ok -> source_discovery:ok -> source_validation:ok -> retrieval_selection:ok -> version_resolution:ok -> evidence_extraction:ok

**Trace id:** `40daac7ea99f400d` (changes every run).

**Known limitation of this demonstration:** runs on a small fictional corpus with lexical retrieval; see README 'Known limitations'.

## Test D - no source (Q10)

**Question:** Describe quantum entanglement experiments.

**Expected behaviour:** NO_SOURCE_FOUND; no evidence; no conclusion; confidence none.

**Actual behaviour:** status `insufficient_evidence`, confidence `none`, professional review required: `True`.  
Answer summary: No evidence-backed answer could be established. No relevant provision was found in the available documents. Status: insufficient_evidence.

**Result:** PASS

**Sources:**
- none

**Evidence (verbatim, verified against source text):**
- none (by design)

**Limitations reported:**
- `NO_SOURCE_FOUND` (blocking): No relevant provision was found in the available documents.

**Pipeline steps:** question_analysis:ok -> source_discovery:ok -> source_validation:skipped -> retrieval_selection:skipped -> version_resolution:skipped -> evidence_extraction:skipped

**Trace id:** `c75e34bb164d4f89` (changes every run).

**Known limitation of this demonstration:** runs on a small fictional corpus with lexical retrieval; see README 'Known limitations'.

## Test E - failed dependency (Q17)

**Question:** What weekly rest is an employee entitled to in Freedonia?  
**Injected failure:** `retriever`

**Expected behaviour:** Retriever is down: status error, failing step visible, no answer from memory.

**Actual behaviour:** status `error`, confidence `none`, professional review required: `True`.  
Answer summary: No evidence-backed answer could be established. The retrieval component failed. (RetrievalError: simulated retriever outage) Status: error.

**Result:** PASS

**Sources:**
- none

**Evidence (verbatim, verified against source text):**
- none (by design)

**Limitations reported:**
- `RETRIEVAL_FAILURE` (blocking): The retrieval component failed. (RetrievalError: simulated retriever outage)

**Pipeline steps:** question_analysis:ok -> source_discovery:failed -> source_validation:skipped -> retrieval_selection:skipped -> version_resolution:skipped -> evidence_extraction:skipped

**Trace id:** `81c58f577ac440be` (changes every run).

**Known limitation of this demonstration:** runs on a small fictional corpus with lexical retrieval; see README 'Known limitations'.

# Custom query extension: 20 to 40

The completed study used 20 queries, five in each of four categories. That met the assignment minimum, but a single query accounts for 20% of a category mean. The extension adds five per category, so one query accounts for 10% of the expanded category mean. This improves breadth; it does not establish a representative or statistically conclusive benchmark.

The 20 additions were designed after examining the original results, then frozen before their own retrieval. They are new information needs, including deliberately related word-sense pairs, rather than extra copies of existing questions. No query will be replaced because its score is inconvenient or its pool has no positive.

| Category | Completed original | New extension | Combined |
| --- | ---: | ---: | ---: |
| Vocabulary mismatch | 5 | 5 | 10 |
| Negation | 5 | 5 | 10 |
| Word sense / homonyms | 5 | 5 | 10 |
| Temporal constraints | 5 | 5 | 10 |
| Total | 20 | 20 | 40 |

## What is ready

Both full-corpus engines have completed the new 20 queries at depth 1,000, producing **20,000 saved hits per engine**. Their symmetric top-20 union contains **707 new query–article pairs**; **184** appear in either engine's top five. All 707 exported article packets match the local corpus exactly. Combined with the original 737 assessed pairs, the completed designated pool has **1,444 assessed pairs**. The full automated suite passes all **153 tests**.

- Original query bytes and all 737 assessments are preserved.
- `queries.all40.jsonl` contains the exact original 20 followed by the new 20.
- `queries.extension20.jsonl` contains only the additions, each with inclusion/exclusion criteria and a 0/1/2 rubric.
- The source protocol records the freeze time and hashes; retrieval uses unchanged BM25 and E5 indexes, with no training or corpus re-encoding.
- New candidates are pooled symmetrically from both engines at depth 20. All707 additions have evidence-backed AI labels; initial, added and combined metrics are published separately.

## Added information needs

| ID | Category | Query |
| --- | --- | --- |
| V06 | vocabulary_mismatch | Find reports about hospitals whose computer files were locked by attackers demanding payment to restore access. |
| V07 | vocabulary_mismatch | Find reports on replacing money paid to leave jail before trial with assessments of whether defendants will return to court. |
| V08 | vocabulary_mismatch | Find reports about longtime neighborhood residents being pushed out as wealthier newcomers move in and rents rise. |
| V09 | vocabulary_mismatch | Find reports about companies moving their legal home or booking profits abroad to reduce taxes owed in their home country. |
| V10 | vocabulary_mismatch | Find reports about school pupils unable to finish internet-based homework because their homes lack reliable online access. |
| N06 | negation | Find reports explaining that research did NOT establish that playing violent video games causes real-world violent crime. |
| N07 | negation | Find reports stating that Malaysia Airlines Flight MH370 had NOT been located despite search efforts or discoveries of possible debris. |
| N08 | negation | Find reports about the Obama administration NOT approving the Keystone XL cross-border permit and instead rejecting it. |
| N09 | negation | Find reports explaining that antibiotics do NOT treat viral infections and discussing why they are still prescribed for them. |
| N10 | negation | Find reports explaining why the FBI did NOT recommend criminal charges against Hillary Clinton in its private-email-server investigation. |
| H06 | homonym | Find reports about security vulnerabilities in Java software and efforts to patch or disable it. |
| H07 | homonym | Find reports about volcanic eruptions on the Indonesian island of Java that caused evacuations or disrupted travel. |
| H08 | homonym | Find reports discussing astronauts or missions in NASA's Mercury human spaceflight program. |
| H09 | homonym | Find reports about mercury contamination in fish or drinking water and the public-health response. |
| H10 | homonym | Find reports about teachers going on strike over pay or working conditions and the effects on schools. |
| T06 | temporal | Find emergency-response actions in Japan during the first 14 days after the March 11, 2011 earthquake and tsunami. |
| T07 | temporal | Find security or investigative actions taken by French authorities during the first 14 days after the November 13, 2015 Paris attacks. |
| T08 | temporal | Find U.S. federal immigration-policy measures announced during the first 30 days after Donald Trump's January 20, 2017 inauguration. |
| T09 | temporal | Find actions Volkswagen took during the first 30 days after the EPA's September 18, 2015 diesel-emissions violation notice. |
| T10 | temporal | Find public-health actions in Brazil during the first 30 days after the WHO's February 1, 2016 Zika-linked emergency declaration. |

## Temporal rules

Every interval excludes the anchor day and includes the specified number of subsequent days. The event date must be established in the article text. A publication date, UUID or undated mention is insufficient. Later retrospective reporting can qualify if it establishes a qualifying action and date. Future plans count only where the query explicitly asks for a formal announcement as the target event.

| ID | Inclusive event window | Anchor source |
| --- | --- | --- |
| T06 | 2011-03-12 through 2011-03-25 | [Primary source](https://www.jma.go.jp/jma/en/2011_Earthquake/Information_on_2011_Earthquake.html) |
| T07 | 2015-11-14 through 2015-11-27 | [Primary source](https://www.justice.gov/archives/opa/pr/attorney-general-loretta-e-lynch-statement-attacks-paris) |
| T08 | 2017-01-21 through 2017-02-19 | [Primary source](https://www.inaugural.senate.gov/58th-inaugural-ceremonies/) |
| T09 | 2015-09-19 through 2015-10-18 | [Primary source](https://www.epa.gov/archive/epa/newsreleases/epa-california-notify-volkswagen-clean-air-act-violations-carmaker-allegedly-used.html) |
| T10 | 2016-02-02 through 2016-03-02 | [Primary source](https://www.who.int/teams/ihr/ihr-emergency-committees/zika-virus-disease-ihr-emergency-committee) |

## Completed evaluation

Read each full available article and grade the exact information need, preserving evidence quotes and offsets. Topic similarity alone is insufficient: silence does not prove a negation, and a related date does not establish the required event window. Keep new labels in a separate versioned file. Do not copy original 57 qrels or original 20 grades onto different queries.

Publish original 20, extension20 and combined 40 separately once the designated extension pool is complete. Use the same linear-gain nDCG@5 and pooled MAP@1000 definitions, retain zero-positive queries, and show per-query scores, category means, win/tie/loss counts and judged coverage. Expanded MAP will still be a shallow-pool estimate.

All707 pairs are assessed, including184 top-five pairs. The combined 40 pool has 1,444 pairs. See [complete results and per-query scores](CUSTOM_40_DEPTH20.md). Original assessments remain unchanged; separate assessor sources and targeted adjudication are archived.

Use paired query differences and descriptive bootstrap intervals. Also resample shared topic families together: cricket, Java and Mercury include related questions. The current family map has 37 labels; it does not establish that the remaining needs are independent. Broader overlaps, including Ebola and marriage-law questions across categories, should be checked in a sensitivity analysis before stronger inference. More queries do not fix label bias, E5 truncation or post-hoc study design.

The four-page submission and supporting report now show initial 20, added 20 and combined 40 results. The demo has 97 distinct queries (57 supplied+40 custom) and retains the original 20 view for comparison. The current comparison is preliminary and uses full-article AI judgments. Human review is planned next; see [assessment method and review plan](ASSESSMENT_METHOD.md).

## Local files and verification

- New BM25 run: `artifacts/runs/bm25-custom40-extension20-v2/`.
- New E5 run: `artifacts/runs/dense-custom40-extension20-v2/`.
- Full-article candidate packet: `artifacts/assessments/custom40-extension20-v2/articles.blinded.jsonl`.
- Candidate IDs/ranks: the same pool directory, `pool.provenance.jsonl`.
- Integrity and coverage result: `artifacts/custom40_extension_validation.json`.

```sh
.venv/bin/python scripts/validate_custom40_extension.py
```

The reproducibility archive includes the new runs and candidate provenance, but excludes full corpus text and full-article packets. Validating article contents requires the existing local dataset and indexes. A fresh extension can be reproduced into unused output directories with the existing `news_ir run` and `prepare_ai_assessment.py` commands; never overwrite the saved original study.

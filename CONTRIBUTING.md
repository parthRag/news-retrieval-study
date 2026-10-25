# Group 5 contribution and review workflow

Course: **Information Retrieval**. Faculty mentor: **Abhinav Kumar**.

The current implementation is imported as an existing project snapshot. Implementation assistance is recorded. The custom comparison uses full-article AI judgments as a preliminary reference; human review is planned next under the [assessment plan](reports/ASSESSMENT_METHOD.md). The following table assigns **component ownership and final-review responsibility**; individual completed work is confirmed separately.

| Member | Student ID | Component responsibility |
| --- | --- | --- |
| Parth Raghuvanshi | 2023A7PS0574P | Data pipeline, BM25 and lexical validation |
| Sushruth Reddy Challa | 2023A7PS0504P | E5 encoding, FAISS and dense-retrieval validation |
| Hamsini G | 2023A7PS0006P | Metrics, custom-query rubrics and judgment audit |
| Kritika Pandey | 2023A7PS0022P | Demo, figures, report and reproduction guide |

Parth's dataset download, Kaggle execution and result handoff are documented in the project session. Specific completed technical work for the other members has not been supplied. Keep the completed-contribution column factual; a planned task becomes completed only after the member does it and records evidence.

## Concrete work to complete now

**Parth:** review `data.py`, `indexing.py` and `retrieval.py`; inspect the tokenizer output for a negation query; run `tests/test_data.py` and `tests/test_bm25.py`; record what was checked and any actual corrections.

**Sushruth:** review `embedding.py`, `dense.py` and `faiss_backend.py`; explain the query/passage prefixes, normalization, 512-token limit and process isolation; run `tests/test_dense.py`; record a reproducible dense-search check without re-encoding the corpus.

**Hamsini:** review `evaluation.py`, `custom_depth20.py` and the assessment protocol; manually review several borderline judgments against their full articles; run `tests/test_evaluation.py`, `tests/test_custom_depth20.py` and `tests/test_quality.py`; record disagreements separately without silently changing frozen labels. This is an independent review only if actually performed by Hamsini.

**Kritika:** use the demo for H02, N03 and T03; check the report tables against `results_snapshot.json`; review all member metadata, page counts and reproduction commands; run `tests/test_demo.py`; record actual usability issues or documentation corrections.

## Recording actual collaboration

Each member should use their own GitHub account and configured Git identity. Create a branch, do the assigned work, and submit a pull request describing the checks, findings and real changes. Link the PR or review note in the completed-contribution matrix. A short review note can be a valid contribution when it documents a real review; no empty edits or invented activity are needed.

Use current timestamps and truthful commit authors. Keep the initial imported snapshot visible. Do not add a member as a co-author solely to divide commit counts; co-author attribution requires that person's actual involvement in that commit. A reviewer who finds no necessary code change can document what was checked instead of manufacturing a fix.

Before submission, each member confirms their own completed-contribution row. Then regenerate the PDFs and package using `DELIVERABLES.md`.

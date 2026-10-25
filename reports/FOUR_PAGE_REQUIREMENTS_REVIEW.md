# Four-page submission report: requirement and accuracy review

The latest request sets an exact four-page target while quoting a six-page maximum. The main submission is `deliverables/5_NewsIR_BM25_Dense.pdf`; the longer research report is supporting material and is not the file to submit for this request.

| Required detail | Location in the four-page report |
| --- | --- |
| Group number and all member names | Page 1, with all four supplied student IDs |
| Project title | Page 1 title; filename uses Group 5 and the short title |
| Primary objective | Page 1, section 1 |
| Evaluation criteria | Page 1, section 2: nDCG, MAP, precision, relevance grades, coverage and uncertainty |
| Dataset with an online link | Page 1, section 2: selected TREC-News mirror, audited corpus counts and separate query sets |
| Related-paper approach and findings, full titles and online links | Page 2, section 3: BEIR, E5, NevIR and RRF |
| Proposed approach and architecture, with reasoning | Page 2, section 4: diagram, component choices, executed preprocessing and input limits |
| Key innovations | Page 4, section 6: constrained queries, traceable judgments, visibility audit and quality experiment |
| Stretch objectives | Page 4, section 6: completed extensions and separately identified future work |
| Key milestones and tentative timeline | Page 4, section 7: actual dates and explicitly tentative review/handoff estimates |
| Current implementation and preliminary quantitative results | Page 3, section 5; implemented demo described on page 4 |
| Memory/time requirements | Page 3, section 5: disk/build/encoding/cold-query measurements; peak RAM is explicitly unmeasured |
| Contribution matrix and delivery plan | Page 4, section 8: responsibility for completed team components, with attribution limits stated |
| Single PDF, correct filename, one submitting member | Page 4 submission note; PDF inspection confirms exactly four pages |

## Accuracy and interpretation checks

Corpus and result counts come from the existing saved artifacts. The original 57-query evaluation and the custom 40-query study are presented separately. Main tables are generated from JSON results rather than copied by hand. Evaluation reproduction checks compare both per-query and aggregate metrics with saved rankings.

The report keeps the following distinctions explicit:

- The custom comparison uses thorough, full-article AI judgments, with human review planned next and not yet completed; custom MAP uses known positives in a shallow pool.
- Unjudged documents contribute zero numerically without being declared confirmed irrelevant.
- E5's category means and individual wins do not establish a general or statistically certain model-family advantage.
- Initial 20 negation nDCG and pooled MAP favored different engines; the combined 40 favors BM25 on both. Semantic matching alone does not impose a logical constraint.
- BM25 indexes full bodies while E5 encodes a 512-token prefix; this coverage difference limits causal explanations.
- Empty-body filtering is a post-hoc top-20 candidate experiment, with no held-out or full-corpus-cleaning claim.
- Index sizes are disk measurements, and the cold-query observation is not a controlled latency benchmark.
- Milestone dates follow saved timestamps converted to Asia/Kolkata. Remaining durations are estimates and do not invent a new deadline.

Paper titles and summarized findings were checked against the primary arXiv, ACL Anthology and author-hosted sources. The PDF inspection checks that the dataset and all four paper links remain clickable after rendering. All four page previews are reviewed for readable tables, intact diagrams and missing or clipped text.

The student-ID correction is **2023A7PS0574P** for Parth; both regenerated PDFs contain it and omit the earlier incorrect ID. The main brief remains four pages. The 40-query evaluation is complete: page 1 states the 1,444-pair preliminary reference and planned human-review stage, and page 3 reports initial 20, added 20 and combined 40 metrics, ten queries per category and family-bootstrap uncertainty. The detailed extension report and frozen rubrics are supplied separately.

## Outstanding information

The public GitHub repository is created and verified at https://github.com/parthRag/news-ir-bm25-dense-final. Completed technical contributions for three members have not been confirmed. These remain accurately marked as pending; the PDF does not invent a repository or member work. The matrix identifies component responsibility without numerical effort shares. This document review does not remove those outstanding submission details.

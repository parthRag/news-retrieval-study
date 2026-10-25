Assessment status: the custom comparison currently uses full-article AI judgments, with human review planned next and not yet completed. See [assessment method and review plan](ASSESSMENT_METHOD.md).

Current expansion: the default view contains40 custom queries, ten per category, with 1,444 preliminary article judgments. Original 20 remains a subset view; original 57 is separate. There are97 distinct evaluated queries across117 saved-view entries. For new examples, use V08 (displacement/article-content failure), N08 (completed versus pending Keystone decision), or V07 (E5 finds the risk-assessment alternative). Combined scores now favor BM25; the older examples below describe the preserved initial 20.

# Running and presenting the retrieval demo

Run this from the repository root:

```sh
.venv/bin/python -m news_ir.demo
```

Open **http://127.0.0.1:8765**. Stop the server with Ctrl+C. If that port is occupied, use `--port 8766` and open the corresponding address. `--root /absolute/path/to/IR` supports launching from another directory. The server listens only on this machine. After reinstalling the editable package, `news-ir-demo` is an equivalent entry point.

The existing Python 3.12 environment, Java 21, corpus, model, indexes and saved artifacts are sufficient. No GPU, paid API, Kaggle credentials or new document encoding is needed. The demo uses local model files with network downloads disabled for live retrieval.

## Saved experiment walkthrough

1. Select **20 linguistic challenges** and a query; press **Compare results**. Two columns show BM25 and E5. Choose 5, 10 or 20 results per engine.
2. Expand **What counts as relevant?** to see the frozen inclusion/exclusion rules. Per-query nDCG@5, pooled AP@1000 and P@5 come from the full saved evaluation; changing display depth does not recalculate them.
3. Click **Read article & evidence**. The dialog displays the full stored title and body, query-specific grade, rationale, self-rated confidence and literal supporting quotations. Evidence is highlighted at saved Unicode offsets.
4. Check **Show only the text retained by E5** to compare the full article with its exact retained passage prefix. The 512-token budget includes the `passage: ` prefix and special tokens. This audit describes input availability, not model attention or a causal explanation of ranking.
5. Select **57 benchmark topics** to compare BM25, E5 and the fixed k=60 RRF hybrid. These grades come from supplied benchmark qrels, separately from custom AI labels. Unjudged results remain visibly unjudged.
6. Scroll to the experiment snapshot for aggregate scores. These are two separate evaluation sets and should not be averaged together.

Suggested demonstration cases:

| Query | What to inspect |
| --- | --- |
| H02: India international cricket | Dense top results include title-only `Results` records; BM25 also retrieves previews instead of requested match outcomes. Inspect the actual text before assigning a cause. |
| N03: reporting that Ebola is not airborne | A strong BM25 win; use exact positive/negative assertions and the rubric to explain relevance. |
| V04: vocabulary mismatch | A strong E5 case; compare substantive evidence with the query wording. |
| T03: state marriage rulings before the national decision | BM25 ranks qualifying accounts higher; distinguish actual rulings, stays and the excluded national decision. |
| V01 or T01, then display 20 | Both engines' top five miss relevant material found deeper in the pooled lists. |

The complete 737-pair assessment preserves every earlier top-five decision. Current custom nDCG uses the deeper pool's ideal ranking, which explains why it differs from the historical top-five report. The custom MAP is a shallow-pool estimate; present it with the review status linked above.

## Live search

Select **Try your own query**, enter a news information need, and press **Search both engines**. A tested example is `jaguar animal habitat conservation`. BM25 runs first, followed by E5 on CPU, then RRF combines both complete top-1,000 lists. Up to 20 results per engine are returned; the current live view displays the first five. A new query has no valid relevance judgments, so live results show no AP, nDCG or invented grades, even when its text resembles a saved query.

On this 8 GiB Mac, engines run sequentially in separate processes and FAISS retains its existing isolation. Only one live job runs at a time. Model/process startup can take around a minute; saved comparisons remain available while it runs. Each engine has a five-minute timeout. Live jobs are temporary memory records and never overwrite experiment rankings, queries or labels.

The verified smoke query took approximately **1.39 seconds for BM25** and **48.59 seconds for E5**, including their separate process startup. Measured engine search intervals were 0.257 s and 23.116 s, respectively. These are single-run operational observations, not a controlled latency comparison; parallel testing and memory pressure can affect them. Browser polling observed completion at about 60 seconds.

## Required local artifacts

Keep `corpus.jsonl` and `artifacts/indexes/bm25/` with its SQLite lookup; `artifacts/indexes/dense/`; `artifacts/models/e5-base-v2/`; the original queries/qrels; `annotations/ai_study_v1/`; and the saved run/evaluation folders. The demo checks source/query/run/evaluation hashes at startup. Moving this project may require updating corpus paths using the documented index relocation support. Downloading code alone does not include the multi-gigabyte data and indexes.

The saved run folders are `bm25-custom-draft-depth1000`, `dense-custom-draft`, `bm25-original-benchmark`, `dense-original` and `rrf-original-k60`. Evaluation folders used by the interface are `custom20-depth20-v1` and `rrf-original-57`.

If startup reports a hash mismatch, inspect the changed artifact and regenerate into a new versioned directory; do not bypass the check or edit the frozen experiment. If live retrieval fails, the error appears in the page and the live slot is released. A missing article body is shown explicitly and is not fetched from the web.

## Verification evidence

`artifacts/demo-validation/validation.json` records the real-browser check: all 77 saved queries at display depth 20, all 77 selected article endpoints, desktop and 390-pixel mobile layout, full-text/evidence consistency, exact input-prefix display, and a real live BM25/E5/RRF query. No browser JavaScript exceptions were observed. Desktop, evidence and mobile screenshots are in the same directory.

To repeat the browser test, first start the server, then run:

```sh
.venv/bin/python scripts/verify_demo_browser.py --output artifacts/demo-validation-recheck
```

This optional check uses the installed Brave Chromium binary by default, creates and deletes a separate temporary browser profile, and runs one real CPU query. `--browser /path/to/chromium` selects a compatible Chromium executable; `--port` selects the demo port. It requires the locked `requests` and `websockets` dependencies and refuses existing output folders. The normal unit suite opens no browser and downloads no model.

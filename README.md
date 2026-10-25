# News Retrieval: BM25 vs. Neural Search

The public repository linked below is a **final submission snapshot**. The working development repository and its existing history are kept private.

Both BM25 and E5 dense search are complete over the same **594,589 articles**. The original **57-query benchmark** and all **40 custom linguistic queries** are evaluated. All **1,444 pairs** in the custom top-20 union have evidence-backed preliminary relevance judgments. A working local demo compares saved experiments, shows full articles and evidence, and supports live BM25/E5/RRF searches. The final local package includes a **four-page submission PDF**, a **19-page research report**, and reproducibility artifacts. See [DELIVERABLES.md](DELIVERABLES.md) for files, reproduction and the metadata still needed before upload.

**Assessment status:** custom comparisons currently use thorough, full-article AI judgments. Human review is planned next and has not yet been completed. See the [assessment method and review plan](reports/ASSESSMENT_METHOD.md).

The post-hoc quality ablation is also complete: removing empty bodies within judged top-20 candidates raises E5 nDCG@5 from 0.4897 to 0.5492. This is separate from the unchanged baseline. See [the quality experiment](reports/QUALITY_ABLATION.md), [custom results](reports/CUSTOM_20_DEPTH20.md) and [hybrid experiment](reports/RRF_EXPERIMENT.md).

The [completed 40-query study](reports/CUSTOM_40_DEPTH20.md) doubles each category from five to ten queries. Initial 20, added 20 and combined 40 results are separate: BM25/E5 combined nDCG@5 is **0.5133/0.4362**, pooled MAP **0.4428/0.4072**. This reverses the initial sample; descriptive query/family intervals still include zero. The original 57 supplied-qrels benchmark favors E5. All 737 initial decisions remain byte-identical. The demo exposes 97 distinct evaluated queries, with the old 20 retained as a subset view. See [the extension protocol](reports/CUSTOM_40_EXTENSION.md).

## Group 5

Course: **Information Retrieval**. Faculty mentor: **Abhinav Kumar**.

| Member | Student ID | Assigned ownership |
| --- | --- | --- |
| Parth Raghuvanshi | 2023A7PS0574P | data/BM25 |
| Sushruth Reddy Challa | 2023A7PS0504P | E5/FAISS |
| Hamsini G | 2023A7PS0006P | evaluation/judgment review |
| Kritika Pandey | 2023A7PS0022P | demo/report |

This allocation assigns ownership and review responsibility, not historical effort. [CONTRIBUTING.md](CONTRIBUTING.md) records the actual-work confirmation process. The public repository is [parthRag/news-retrieval-study](https://github.com/parthRag/news-retrieval-study); code, notebooks, preprocessing scripts and reports are published. See [the GitHub handoff](reports/GITHUB_HANDOFF.md).

Download the four-page PDF, supporting research report and portable reproducibility archive from the [submission release](https://github.com/parthRag/news-retrieval-study/releases/latest). The public snapshot and archive include saved rankings for numerical reproduction; corpus, model and indexes remain local dependencies. To verify a source checkout without the archive, run `PYTHONPATH=src python scripts/validate_final_deliverables.py`; its root `PACKAGE_MANIFEST.json` binds the exported files.

## Run the demo

From this repository, with the existing corpus, indexes and model files:

```sh
.venv/bin/python -m news_ir.demo
```

Open **http://127.0.0.1:8765**. Saved experiments load immediately; a new CPU search can take around a minute including model startup. No new GPU job or API credentials are required. Read [the demo guide](reports/DEMO_GUIDE.md) for presentation examples, required files and timing limits. Live queries are unjudged and never change the frozen experiments.

## Environment

Use Python 3.12 and Java 21. The application automatically selects an installed Java 21 on macOS if `JAVA_HOME` is unset; it does not modify your shell configuration. An explicit `JAVA_HOME` is respected. The JVM heap is capped at 2 GiB.

The project environment lives in `.venv`. To recreate it:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
```

The lock records the tested dependency versions on this ARM Mac. Other operating systems may require platform-specific dependency adjustments. A first installation can instead use `pip install -e '.[test,dense]'`; the lock is preferred for reproducing this environment.

## Build and search

Run commands from the project root:

```sh
.venv/bin/news-ir index --corpus corpus.jsonl --output artifacts/indexes/bm25
.venv/bin/news-ir search "cricket insect lifecycle" --top-k 5
.venv/bin/news-ir analyze "events that did NOT happen without warning in 2016"
.venv/bin/news-ir document b2e89334-33f9-11e1-825f-dabc29fd7071
.venv/bin/news-ir verify --sample-size 1000
```

Indexing streams directly from the source JSONL into Lucene and a SQLite byte-offset table. It does not create a second copy of the article text. Titles and full bodies are concatenated with a newline, with no title boost. Documents with both fields whitespace-empty are excluded from retrieval but remain available by ID; title-only and body-only documents are retained. IDs are strings and must be unique.

The English analyzer lowercases/tokenizes text, preserves stopwords, and does not stem. The same analyzer is applied to queries. BM25 uses fixed `k1=0.9`, `b=0.4`. Text such as `NOT` is treated as a query term; there is no hard Boolean negation or date filter. Preserving negation words does not make a bag-of-words scorer reason about negation. The `analyze` command exposes the actual tokens.

Single-query output is JSON containing ranked IDs, scores, titles, leading-body snippets, analyzed terms, and search latency. A snippet is only a preview, not a relevance rationale. `document` returns the original full title and body. Normal source checks detect changes in file size/modification time; `verify` checks the complete SHA-256. Moving a corpus is supported through `--corpus`, with a full hash check of the relocated file.

## Export a query suite

Queries are JSONL objects with unique string `_id` and string `text` fields. Empty query text is allowed and produces an explicit empty result record. For the downloaded 57-query supporting benchmark:

```sh
.venv/bin/news-ir run --queries queries.jsonl --output artifacts/runs/bm25-original --top-k 1000
```

The output directory contains:

- `run.trec`: six-column TREC ranking file.
- `results.jsonl`: every query, its tokens, latency, and ranked hits, including empty lists.
- `queries.jsonl`: a snapshot of the exact query IDs/texts used.
- `manifest.json`: source/query/index/run hashes, parameters, retrieval depth, timing protocol, and counts.

Existing index/run directories are never silently overwritten. To rebuild, choose a new output directory and pass it with `--index` when searching. Failed builds/runs remove only their own temporary output directory and do not publish incomplete artifacts. Source files are never edited.

The `run` command exports rankings. Use `evaluate` below to calculate metrics. The downloaded qrels apply to the original 57 queries only; the custom queries require their own relevance reference, described above.

## Original 57-query evaluation

| Metric | BM25 | E5 dense | RRF hybrid |
| --- | ---: | ---: | ---: |
| nDCG@5, supplied grades as gains | 0.3975 | 0.4576 | 0.4900 |
| MAP@1000 | 0.2329 | 0.2765 | 0.3332 |
| Recall@1000 | 0.6681 | 0.7738 | 0.8044 |

E5 has higher averages on this benchmark, while BM25 wins 21 of 57 nDCG@5 comparisons. The paired bootstrap interval for the nDCG@5 difference includes zero. Existing judgment coverage differs between systems; unjudged articles are not confirmed irrelevant. See the [full report](reports/ORIGINAL_57_BENCHMARK.md), [case studies](reports/ORIGINAL_57_CASE_STUDIES.md) and [per-query CSV](artifacts/evaluations/original-57/per_query.csv).

To evaluate the saved runs into a new directory:

```sh
.venv/bin/news-ir evaluate --output artifacts/evaluations/original-57-rechecked
.venv/bin/python scripts/report_original_benchmark.py
```

The evaluator retains unavailable positives in its main denominators, reports alternative gains and available-corpus sensitivity, and cross-checks all scores against native `trec_eval` bundled with Anserini. Original runs, qrels and corpus are preserved. Run and evaluation outputs have manifests and hashes; existing output directories are never silently overwritten.

The hybrid combines saved ranks using `1/(60+rank)` from each engine, without tuning or another encoding job. Its nDCG difference interval against E5 includes zero, despite higher means. See [the hybrid report](reports/RRF_EXPERIMENT.md) for uncertainty and four evaluation policies. Reproduce it into fresh directories:

```sh
.venv/bin/news-ir fuse --output artifacts/runs/rrf-original-k60-new
.venv/bin/python scripts/evaluate_fusion.py --fusion-run artifacts/runs/rrf-original-k60-new --output artifacts/evaluations/rrf-original-57-new
.venv/bin/python scripts/report_current_study.py
```

The custom study uses its own preliminary reference, separate from the original qrels; the assessment status and review plan are linked above. [The assessment protocol](annotations/README.md) records full-article evidence, source hashes, confidence and coverage. The preserved initial 20 top-20 union contains 737 assessed pairs. Historical initial results are:

| Custom 20 metric | BM25 | E5 dense |
| --- | ---: | ---: |
| nDCG@5, linear 0–2 gains | 0.462126 | 0.489668 |
| Pooled MAP@1000 | 0.400600 | 0.468318 |
| Precision@5 | 0.530000 | 0.530000 |

Both paired difference intervals include zero. MAP uses known positives in the shallow pool; only about 3% of each top-1,000 ranking is judged. V05 has no positive in the pool and remains in the macro average. E5 wins three negation queries and BM25 two at nDCG@5; BM25 has higher negation pooled MAP and higher temporal category means. See [the complete results and limitations](reports/CUSTOM_20_DEPTH20.md) and [all 737 evidence-backed decisions](reports/CUSTOM_20_DEPTH20_EVIDENCE.md).

```sh
.venv/bin/python scripts/validate_custom_depth20.py
.venv/bin/python scripts/evaluate_custom_depth20.py --output artifacts/evaluations/custom20-depth20-rechecked
.venv/bin/python scripts/report_custom_depth20.py
```

The evaluator requires complete designated-pool coverage, validates every evidence span, and preserves all 188 earlier decisions. All 588 native metric comparisons passed. The [earlier top-five result](reports/CUSTOM_20_TOP5.md) is preserved: its nDCG differs because deeper judgments change the ideal-ranking denominator; the top-five grades, ranks and P@5 are unchanged. Group 5, member IDs, course and mentor are filled. The GitHub repository is public; confirm individual completed-work attribution before submission.

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
.venv/bin/news-ir verify --sample-size 1000
```

Tests exercise real Lucene indexes, an independent BM25 score calculation, analyzer behavior, ranking/ties, Unicode byte offsets, concurrent document reads, malformed data, duplicate IDs, failed-build cleanup, source identity, run export, and the CLI. They require the Java/Pyserini environment; they do not download models or access the network.

Detailed measured results are recorded in `reports/TASK_A_PROGRESS.md` once full-corpus validation is complete. Corpus and original proposal files are excluded from code commits; dataset distribution follows the corpus's actual terms.

## Dense retrieval and the GPU job

The full Kaggle index is installed and verified: **594,589 articles**, matching BM25. Both engines have top-1,000 rankings for the same 20 custom queries. See [KAGGLE_RETURN_VALIDATION.md](reports/KAGGLE_RETURN_VALIDATION.md) for the original handoff validation and [the current assessment status](reports/CUSTOM_20_DEPTH20.md). No further GPU job is needed for the demo, saved-run fusion or article assessment.

For Kaggle, use [KAGGLE_SETUP.md](reports/KAGGLE_SETUP.md), import [News_IR_Kaggle_Encoding.ipynb](notebooks/News_IR_Kaggle_Encoding.ipynb), and attach `artifacts/bundles/news_ir_kaggle.zip` as a private Dataset. No API credentials are needed. The job saves timed checkpoints and can resume from a previous saved notebook output before building the full index.

Use [COLAB_SETUP.md](reports/COLAB_SETUP.md) with [News_IR_Dense_Encoding.ipynb](notebooks/News_IR_Dense_Encoding.ipynb) and `artifacts/bundles/news_ir_colab.zip`. The notebook checks source/model identity, saves resumable Drive shards, builds full-corpus FAISS search, and exports draft query rankings. Free Colab GPU availability is not guaranteed; no paid plan is needed to try it.

The local real-model pilot is usable explicitly as a pilot:

```sh
.venv/bin/news-ir dense-search "Virginia Tech Sugar Bowl receivers" --index artifacts/indexes/dense-pilot --allow-partial --device cpu
```

The complete index is installed at `artifacts/indexes/dense`. To search or create a fresh local run, use:

```sh
.venv/bin/news-ir dense-search "cricket insect lifecycle" --top-k 5
.venv/bin/news-ir run --engine dense --queries annotations/custom_queries.draft.jsonl --output artifacts/runs/dense-custom-draft-local --top-k 1000 --device cpu
```

For a full local encoding run, `news-ir encode` defaults to the entire eligible corpus. `--limit` explicitly creates a pilot, and pilot indexes require `--allow-partial` to build/search. `--resume` verifies committed shards and continues their source offsets. Example full commands:

```sh
.venv/bin/news-ir encode --output artifacts/encodings/e5-base-v2 --batch-size 8
.venv/bin/news-ir dense-index --encodings artifacts/encodings/e5-base-v2 --output artifacts/indexes/dense
```

The model uses pinned E5 weights, query/passage prefixes, a 512-token total budget, masked mean pooling, and L2 normalization. FAISS performs exact inner-product search over normalized vectors. It runs in an isolated process to avoid PyTorch/FAISS OpenMP conflicts on macOS; no unsafe duplicate-library overrides are used. Query encoding and FAISS IPC/search are included in dense run latency.

The original draft, blank query-review sheet, frozen assessment protocol and pilot decisions are under `annotations/`. [TASK_B_PROGRESS.md](reports/TASK_B_PROGRESS.md) records the earlier engine milestone. These historical pilots have different scopes; completed custom results are reported separately above. Human article-level review will be recorded in `annotations/human_review/`.


## Verify the completed 40-query extension

The expanded artifacts preserve source ranks, scores and the original 737 judgments. The added707 preliminary decisions include literal evidence and a targeted audit; human review follows the plan linked above. Check against local full articles and recompute both gain modes and topic-family intervals:

```sh
.venv/bin/python scripts/validate_custom40_extension.py
.venv/bin/python scripts/validate_expanded_study.py
```

`artifacts/evaluations/custom40-depth20-v2/` contains combined metrics, category results, sensitivities and family intervals; the separate `custom40-extension20-depth20-v2/` folder contains follow-up-only scores. Saved combined runs preserve both component rankings and hashes. `scripts/evaluate_expanded_study.py` refuses to overwrite existing evaluations.

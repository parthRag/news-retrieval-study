# Task A: BM25 engine, document access, and verification

Completed on 19 October 2026. This is an implementation progress record, not the final comparative research report. Task A means Engine A (classic BM25), the shared document-access foundation, and reproducible retrieval exports.

## Outcome

The lexical engine works on the complete downloaded corpus. It indexed 594,589 searchable articles from 594,977 records, excluding only 388 articles with both title and body whitespace-empty. All source records, including those empty articles, remain available by exact ID through the document store. No source dataset or proposal content was changed.

The implementation passed 51 automated tests and a full Lucene integrity check. The 57 supplied original queries each returned 1,000 hits. All 57,000 exported hits were checked against both the TREC/JSONL representations and source-document access. Repeating the query run produced an identical TREC ranking file.

## What was implemented

| Component | File | Purpose |
|---|---|---|
| Project package and command | `pyproject.toml`, `src/news_ir/cli.py` | Installable package and `news-ir` command |
| Process-local Java setup | `src/news_ir/runtime.py` | Select installed Java 21 on macOS, cap JVM heap, route Java logs to stderr |
| Source data and document lookup | `src/news_ir/data.py` | Validate records/queries, preserve string IDs, read full articles using byte offsets |
| Streaming index builder | `src/news_ir/indexing.py` | Feed Lucene in batches and build the SQLite offset table in one source pass |
| BM25 interface | `src/news_ir/retrieval.py` | Analyze/search queries, validate parameters, expose ranked IDs and article lookup |
| Batch exports and verification | `src/news_ir/experiments.py` | TREC/JSONL runs, query snapshots, manifests, source hash/count checks |
| Regression and integration tests | `tests/` | Exercise real Lucene indexes and failure behavior |
| Full-run validation | `scripts/validate_task_a.py` | Check every exported rank, ID lookup, and repeat-run agreement |
| Reproduction instructions | `README.md`, `requirements-lock.txt` | Commands and the exact tested dependency versions |

The pre-existing `scripts/audit_dataset.py` remains the source audit; it was not repurposed into the retrieval engine. `PROJECT_BLUEPRINT.md` now records Task A's completion and the remaining project work.

## Retrieval design and rationale

**Scoring:** Lucene BM25 through Anserini/Pyserini, with fixed `k1=0.9` and `b=0.4`. No settings were tuned against the 57 topics or the forthcoming custom judgments. Title and complete body are concatenated once with a newline and indexed without field boosts.

**Analysis:** the English analyzer tokenizes and lowercases, keeps stopwords, and does not stem. The exact same analyzer is applied to queries. A recorded probe maps `NOT without running 2016 cricket` to `not`, `without`, `running`, `2016`, `cricket`. Preserving these terms prevents the preprocessing stage from silently deleting the negation cue; it does not give BM25 logical negation capabilities. Natural-language `NOT` is a term, not a hard Boolean filter. There is no extra temporal filter or word-sense classifier.

**Storage:** Lucene stores the inverted retrieval representation. SQLite stores document ID, byte offset, record length, and eligibility. Full text is read from the unchanged source with positional reads, preserving UTF-8 byte boundaries. Reads are protected for concurrent document lookup. The system does not create a duplicate 2.45 GB text corpus.

**Eligibility:** keep title-only/body-only articles and preserve IDs as strings. Exclude only records whose title and body are both whitespace-empty. There are 15,984 title-only source articles, which remain searchable. This eligible-document policy must also be used by the later dense engine for a fair corpus comparison.

**Reproducibility:** each index records corpus SHA-256, size, modification time, counts, analyzer, parameters, runtime versions, and build settings. Each batch run adds input and snapshot query hashes, the index manifest hash, output hashes, retrieval depth, and timing protocol. Ranking ties follow Anserini's external-ID handling. Its search API rounds scores to 1e-4 and adjusts ties; returned scores should not be mistaken for unrounded term weights.

**Failure handling:** reject malformed records, duplicate document/query IDs, invalid parameters, and changed sources. Existing output directories are protected from silent overwrites. Work is built in a private temporary directory and published only after completion. Caught failures clean up only their own temporary output. Fast source checks use size/mtime; the verification command independently hashes the complete source. Relocated corpus copies require hash equality.

## Issues found and resolved during review

1. Pyserini 1.5's general Python search import eagerly loads API encoders and initializes an API client. This caused local BM25 startup to fail without credentials. The implementation now uses the same `io.anserini.search.SimpleSearcher` through Pyserini's Java bridge. It does not import those encoders, supply dummy credentials, or call an external API. Regression tests exercise this path without API keys and confirm the encoder/API modules are absent.
2. The first independent score comparison detected the upstream score-rounding behavior. The final test separately compares raw term weights with the hand-calculated Lucene BM25 expression and verifies the exported rounded search score. It checks actual formula agreement rather than merely asserting a plausible ordering.
3. Java indexer logs initially shared stdout with machine-readable output. Java output is now routed to stderr. A subprocess test verifies that the index and search commands emit parseable JSON on stdout.
4. Review added checks for changed corpus content, incompatible analyzer/schema/count metadata, duplicate IDs, and failed-build publication. Closing the search engine also closes document resources even if Java cleanup fails.

## Automated verification

Run:

```sh
.venv/bin/python -m pytest -q --junitxml=artifacts/test-results.xml
```

The completed suite contains 51 passing cases covering:

- Independent BM25 IDF, term-frequency, and length-normalization calculation on a controlled short-document collection.
- Matching query/index analysis, preserved negation/numbers/inflections, and handling of punctuation-only or empty queries.
- Context-sensitive lexical ordering for the sports/insect senses of cricket, title-only/body-only retrieval, and exact Unicode IDs/text.
- Stable ties, top-k boundaries, absent terms, finite/valid BM25 parameters, and explicit closed-resource errors.
- Byte-offset lookup for every tiny-fixture record, missing IDs, SQL-looking IDs, and concurrent reads.
- Malformed JSON/field types, duplicate source/query IDs, empty corpora, and corpora containing only empty articles.
- Successful cleanup after failed builds, overwrite protection, copied-source hash validation, and full verification of same-length source modifications with preserved mtime.
- Rejection of incompatible index metadata, exact TREC serialization, query snapshots, explicit zero-hit query records, reproducible ranking files, and CLI exit codes/output.
- Local BM25 operation without loading API encoders or requiring credentials.

Dependency validation with `.venv/bin/python -m pip check` also passed. These are correctness tests, not a claim about search relevance on the custom assignment queries.

## Full-corpus evidence

| Check | Measured result |
|---|---:|
| Source records | 594,977 |
| Searchable/indexed articles | 594,589 |
| Empty records excluded from search | 388 |
| Title-only records retained | 15,984 |
| Build time, excluding dependency/JVM startup | 66.548 seconds |
| Lucene files, logical size | 326,696,639 bytes / 311.56 MiB |
| SQLite offset store, logical size | 58,785,792 bytes / 56.06 MiB |
| Full source SHA-256 verification | Passed; matches original audit |
| SQLite integrity | Passed |
| Deterministic random lookup sample | 1,000 records passed |
| Full Lucene `CheckIndex` | No problems detected |
| Original query count | 57 |
| Results per original query | 1,000 |
| Exported hits checked | 57,000 |
| Distinct ranked documents checked | 50,339 |
| Repeat TREC run | Byte-identical |

The corpus SHA-256 is `82086c5dc9397700ca6682d19f1a1cace8ace5defa31f7990ca3c28314ec61a9`. The repeatable TREC run hash is `ead8071494f6aa790c771c6927e04117dc62d978d3f4cfe338313aaaf4920cb1`.

Evidence files:

- `artifacts/indexes/bm25/manifest.json`
- `artifacts/test-results.xml`
- `artifacts/task_a_verification.json`
- `artifacts/lucene_check.log`
- `artifacts/task_a_run_validation.json`
- `artifacts/runs/bm25-original/` and `artifacts/runs/bm25-original-repeat/`
- `artifacts/task_a_search_example.json` and `artifacts/task_a_analyzer_example.json`

The runtime is Python 3.12.9, Temurin Java 21.0.4, and Pyserini 1.5.0 on the local ARM Mac, with four indexing threads. The Java heap cap is 2 GiB; this is not a measurement of total process memory.

## Observed search latency

The first full query run overlapped index integrity checks and tests. Its mean was 157.29 ms and median 121.70 ms. Those values include deliberate contention and should not be presented as an isolated latency benchmark.

A second sequential run after those checks produced the same rankings with mean **33.76 ms**, median **27.37 ms**, minimum **17.75 ms**, and maximum **254.42 ms**, at top-1,000 depth. Timings include query analysis/search, but exclude JVM startup, source-article lookup, JSON serialization, and a future UI. The second run benefits from OS caches and is a local observation, not a hardware-independent throughput claim. JSONL timing records preserve individual query measurements.

## Try the completed engine

```sh
.venv/bin/news-ir search "cricket insect lifecycle" --top-k 5
.venv/bin/news-ir analyze "NOT without running 2016 cricket"
.venv/bin/news-ir document b2e89334-33f9-11e1-825f-dabc29fd7071
.venv/bin/news-ir verify --sample-size 1000
```

For a new query file, use a new output directory:

```sh
.venv/bin/news-ir run --queries annotations/custom_queries.jsonl --output artifacts/runs/bm25-custom --top-k 1000
```

That custom query file does not yet exist; this illustrates the next workflow. The already completed supporting runs can be checked again with:

```sh
.venv/bin/python scripts/validate_task_a.py
```

## Interpretation and remaining work

The engine is operational and reproducible. For example, the supplied minor-league baseball query ranks a wage-lawsuit article first, and the opioid-distributor query ranks a DEA enforcement investigation first. These are inspectable retrieval examples, not new relevance judgments or evidence of overall effectiveness.

The cricket-insect example retrieves insect-related articles, but the leading article concerns edible insects rather than necessarily explaining a lifecycle. This illustrates why word-sense plausibility alone is insufficient: the full information need still needs judgment. Do not declare an article relevant from its matching words or title alone.

Remaining required tasks are the dense engine, the 20 custom queries and rubrics, symmetric candidate pooling, reviewed custom judgments, nDCG@5/MAP evaluation, the comparison demo, and the final research report. The existing 57-query background-linking qrels are not labels for the new custom suite. No custom relevance scores have been produced or claimed in Task A. BM25's settings and source eligibility are now available for the dense comparison to match.

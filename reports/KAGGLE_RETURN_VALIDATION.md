# Completed Kaggle run and local integration

Status on 24 October 2026: the full E5 index has been returned, verified and installed locally. Both BM25 and dense search now cover the same **594,589 eligible articles**. The retrieval infrastructure is available; custom relevance evaluation and the comparison demo remain to be completed.

## Returned computation

| Item | Verified result |
| --- | ---: |
| Eligible articles encoded | 594,589 / 594,589 |
| Coverage | Full |
| Vector dimension and precision | 768, float32 |
| GPU | One Tesla T4 |
| Full encoding session | 20,574.82 seconds, approximately 5 h 43 min |
| Pure shard encoding time | 20,551.12 seconds |
| Custom draft queries exported | 20 |
| Ranking depth | 1,000 per query |
| Returned ranking hits | 20,000 |

The cloud runtime was Python 3.13.15, PyTorch 2.9.1+cu126, Transformers 5.20.1 and FAISS 1.13.2. E5 used the pinned revision `f52bf8ec8c7124536f0efb74aca902b2995e5bcd`, its query/passage prefixes, a 512-token total input budget, attention-mask-aware mean pooling and L2 normalization. The same title-plus-body eligibility policy as BM25 was retained.

The initial 128-article warm benchmark projected 4.92 encoding hours. The actual full session took 5.72 hours, illustrating the limits of extrapolating from an initial sample. These timings describe encoding, not model training or a controlled comparison of retrieval speed.

## Integrity and mathematical checks

The downloaded archive SHA-256 exactly matches `job_summary.json`:

```text
23f1cf7a149882a640372fc794153ff7a228ddf079970c9f4a4c52069b1aafd9
```

The archive was extracted into a staging directory and checked before its new index/run folders were published under `artifacts/`. Existing pilot and BM25 artifacts were retained. Original cloud manifests were preserved, including hashes and provenance paths.

Validation checked:

- The actual local corpus SHA-256 against the cloud source identity, BM25 metadata and run manifest.
- Every required local model/tokenizer file against its hash and the returned model configuration.
- **All 594,589 dense IDs**, including exact order, uniqueness and agreement with BM25's eligible-document table.
- **All 594,589 vectors** for expected dimension, finite values and unit norms. Maximum unit-norm error was **1.19e-7**.
- The exact FAISS `IndexFlatIP` type and inner-product metric.
- **All 20,000 returned hits** for eligible IDs, unique documents per query, contiguous ranks, descending finite scores, consistent TREC/JSONL representations and file hashes.
- All 20 query IDs/texts against the local draft suite and returned snapshot.
- **1,391 source article lookups**, combining a fixed random sample with top-20 retrieved documents.
- Local offline CPU search for the first pre-existing query in each of the four categories, with repeated-search agreement.
- Independent NumPy cosine calculation over the full document matrix for those four query vectors. Exact top-five ID order agreed for **all four**, with maximum score difference **6.56e-7**.
- The default local CLI paths with `cricket insect lifecycle`. It returned five full-corpus results, led by “Gateway bug: How crickets could hook America on eating insects.” This is a smoke check, not a gold relevance label.

The full validation is reproducible from the project root:

```sh
.venv/bin/python scripts/verify_dense_return.py
```

FAISS validation runs in a separate process from PyTorch to preserve macOS OpenMP isolation. Evidence is in `artifacts/task_b_full_validation.json`. These checks establish artifact integrity and mathematical retrieval consistency; four search probes are not a relevance evaluation of the 20-query suite.

## Installed artifacts and matching BM25 export

| Location | Contents |
| --- | --- |
| `artifacts/indexes/dense/` | Verified full cosine-search index and ID mapping |
| `artifacts/runs/dense-custom-draft/` | Original Kaggle top-1,000 rankings for all 20 drafts |
| `artifacts/gpu_benchmark_kaggle.json` | Original GPU throughput measurement |
| `artifacts/runs/bm25-custom-draft-depth1000/` | Newly exported BM25 rankings at the same depth |
| `artifacts/matched_draft_runs_validation.json` | Shared source/query identity and 20,000-hit validation |
| `artifacts/full_dense_search_example.json` | Successful default-path local CLI result |
| `artifacts/full_dense_cli_check.json` | CLI smoke-check runtime and coverage |
| `artifacts/test-results-full-dense-return.xml` | Automated regression results: **89 passed**, zero failures/skips |

The earlier BM25 draft export contained only 20 hits per query. A new directory supplies 1,000 per query without replacing that earlier evidence. Both current exports use the exact same query snapshot and full eligible corpus. This prepares balanced candidate pooling once the suite is reviewed and frozen. If review changes a query, rerun the affected suite before final assessment.

The original cloud manifest records temporary Kaggle model/document paths. The local CLI supplies the existing Mac model and document metadata, so importing the index does not require changing its manifest. Direct Python use of `DenseEngine` should likewise supply `document_index` and `model_dir` explicitly.

To search locally:

```sh
.venv/bin/news-ir dense-search "cricket insect lifecycle" --top-k 5 --device cpu
```

The Mac has **8 GiB of RAM**. Raw vectors alone occupy approximately 1.70 GiB, in addition to model, IDs and application overhead. Full-index validation completed, but startup and full scans can be slow under memory pressure. The cold CLI smoke check took **32.15 seconds including startup**; this single run is not a controlled latency benchmark. Account for memory use in the combined demo. Cloud dense timings and local BM25 timings must not be treated as a controlled speed comparison.

## What remains

1. Review intents, exclusions and event windows with the group; confirm corpus support and freeze the suite.
2. Pool equal-depth candidates from the two full-corpus engines, hide engine/rank information from assessors and collect actual relevance judgments.
3. Calculate nDCG@5 and MAP@1000 with the specified grading convention and explicit treatment of unjudged documents.
4. Build the comparison demo, including article inspection and per-query failure analysis.
5. Write the research report with actual results, uncertainty and limitations, including dense 512-token truncation versus BM25's full article input.

No custom gold labels, nDCG/MAP scores or engine-effectiveness conclusions were generated by this import. Retain the original archive and saved Kaggle checkpoints until local integration is accepted.

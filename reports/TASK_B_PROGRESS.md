# Task B: E5 dense retrieval, query drafts, and the full-corpus GPU job

> Historical milestone: current assessment status and planned human review are described in [Assessment method](ASSESSMENT_METHOD.md).

Status on 24 October 2026: the **full 594,589-document neural index is encoded, returned from Kaggle, verified and installed locally**. BM25 and dense search cover the same eligible corpus. The current regression suite passes **107 tests**, with no failures or skips. The original 57-query evaluation is also complete; see [TASK_C_PROGRESS.md](TASK_C_PROGRESS.md). See [KAGGLE_RETURN_VALIDATION.md](KAGGLE_RETURN_VALIDATION.md) for actual GPU runtime, full-index validation, installed files and remaining work. Earlier handoff/pilot sections below are historical implementation records.

## Kaggle handoff added on 24 October

Import `notebooks/News_IR_Kaggle_Encoding.ipynb`, attach `artifacts/bundles/news_ir_kaggle.zip` as a private Dataset, and follow [KAGGLE_SETUP.md](KAGGLE_SETUP.md). No API credentials are needed. The approximately 34 MB bundle includes the actual project implementation and compact document metadata; the public corpus and pinned model are downloaded and hash-verified in Kaggle.

`scripts/run_kaggle_dense.py` handles both intact and automatically extracted Dataset ZIPs. Dependencies use a separate environment and an explicit PyTorch 2.9.1 CUDA 12.6 wheel; the setup checks an actual CUDA operation. This cloud runtime differs from the Mac runtime and is recorded in shard metadata. The driver benchmarks the allocated GPU, encodes the full corpus, builds the FAISS index, and returns `dense-results.zip` plus `job_summary.json` when finished.

Encoding now accepts an optional time budget, checked after each committed shard. An unfinished job reports `completed: false` while retaining its full-corpus target. The driver exports `dense-checkpoints.zip` for resumption from a saved notebook output or another private Dataset. Resume verifies shard hashes and configuration before continuing. This is separate from `--limit`, which still selects a pilot. Completed outputs go under `/kaggle/working`; temporary downloads go under `/kaggle/temp`. Saved-version execution is used to preserve outputs, with conservative budgets to allow finalization before the provider's session limit.

Validation includes an end-to-end fixture job that stops, exports a checkpoint, restores it into another output directory, completes encoding, builds real FAISS search and exports query rankings. Only remote downloads, GPU allocation and embedding inference are mocked in that handoff test. Additional checks cover timed-stop/full-target semantics, extracted checkpoint inputs, corrupt/traversing archives, metadata relocation and Unicode lookup, missing GPU rejection, notebook code syntax, and reuse of completed outputs. The existing real-E5 and BM25 regression tests also pass. Evidence: `artifacts/test-results-kaggle.xml` and `artifacts/kaggle_handoff_validation.json`.

At handoff preparation time the cloud run was pending. It has since completed on a Tesla T4: 594,589 articles in approximately 5 h 43 min, with verified saved output and local integration. No custom relevance labels or final effectiveness metrics have been produced.

### Hosted Python 3.13 setup correction

The first Kaggle attempt reported that standard `venv` creation failed inside `ensurepip`, before encoding began. The dependency cell now creates the environment with `--without-pip` and bootstraps pip using PyPA's official `get-pip.py`. This changes only the notebook setup; the uploaded bundle and job configuration remain compatible. Internet access is required for the bootstrap download.

The updated handoff tests pass **12/12**, including execution of the actual setup cell with package installations mocked and a real pip-free environment with `ensurepip` deliberately unavailable. A separate check used **Python 3.13.4**, blocked `ensurepip`, created a real environment and ran the downloaded official bootstrap against an offline pip wheel successfully. Evidence: `artifacts/test-results-kaggle-setup-fix.xml` and `artifacts/kaggle_python313_setup_validation.json`. This verifies environment creation and pip installation, not cloud CUDA execution.

## Implemented behavior

`embedding.py` downloads E5-base-v2 at an immutable model revision and hashes the required tokenizer/config/weights files. Searches load those local files with remote code disabled and require no external API. The revision used is `f52bf8ec8c7124536f0efb74aca902b2995e5bcd`.

Inputs use `query: ` and `passage: ` prefixes. The total input budget is 512 tokenizer tokens, including prefix/special tokens. Documents use the same title-plus-body text and eligible IDs as BM25, with the beginning retained when truncation is required. Embeddings use attention-mask-aware mean pooling and L2 normalization. Inference is float32, with model training/dropout disabled. These choices follow the [E5 model documentation](https://huggingface.co/intfloat/e5-base-v2).

`dense.py` encodes source articles in shards. Each committed shard contains float32 vectors, its exact ordered IDs, source offsets, encoding settings/runtime, and file hashes. Shards are published after successful completion. Resume verifies them and rejects incompatible corpus/model/shard-size/selection settings. Batch size and hardware can change between sessions; per-shard runtime records identify the actual environment. Uncommitted temporary shards are not used as completed output.

Index construction validates the ordered encoded IDs against the BM25 source eligibility table, then builds FAISS `IndexFlatIP`. With normalized vectors this performs exact cosine ranking. Cutoff ties expand before external-ID sorting, so selecting only some tied neighbors does not make the ordering depend on FAISS's default tie selection. The shared run exporter now supports both engines and records dense model/runtime and coverage metadata.

Partial encoding is explicitly marked `pilot`. Building/searching a partial index requires `--allow-partial`; it cannot be silently presented as the full-corpus experiment.

## Native-library issue found during testing

The first combined test run exposed a macOS OpenMP conflict when PyTorch and the FAISS wheel were initialized in one process. Instead of using an unsafe duplicate-library override, all FAISS construction/search now runs in a separate process. A search engine keeps its worker alive between queries and closes it with the engine. The parent handles E5 inference and article access; the worker handles only FAISS/NumPy and a small JSON request/response protocol.

This also keeps the encoding/vector-search path independent of Java and Pyserini imports. A dedicated test blocks Pyserini imports to check portability for the lighter Colab environment. BM25 still uses its original tested Java path.

## Local measurements and validation

| Measurement | Result |
|---|---:|
| CPU warm benchmark | 16 articles in 3.559 s, about 4.50 articles/s |
| CPU encoding-only extrapolation | About 36.7 hours |
| Native Apple MPS warm benchmark | 64 articles in 4.924 s, about 13.00 articles/s |
| MPS encoding-only extrapolation | About 12.7 hours |
| Completed real-model GPU pilot | 512 articles, four 128-article shards |
| Pilot encoding time | 37.54 s, excluding model startup |
| Pilot vector dimension | 768 |
| Largest measured unit-norm error | 1.19e-7 |
| Source document lookups checked | All 512 |
| FAISS versus brute-force real-model query checks | Three passed |
| Automated suite | 71 passed, zero failures/skips in this workspace |

The benchmarks use initial eligible articles with warmup and different sample sizes, so they are resource-planning estimates rather than a controlled CPU/GPU research comparison. Full runtime may vary. The sandbox could not see MPS; the native benchmark and pilot used approved access outside the sandbox. CUDA/Colab speed has not yet been measured, and the notebook does not claim a guaranteed GPU allocation or runtime.

The three pilot title queries ranked their own source articles first and agreed with direct cosine calculation. This is a useful integration sanity check, not a full-corpus relevance result. Draft queries were also exported against the pilot to exercise the dense CLI, explicitly recording partial coverage.

Evidence:

- `artifacts/test-results-task-b.xml`
- `artifacts/dense_benchmark_cpu.json`
- `artifacts/dense_benchmark_native.json`
- `artifacts/encodings/e5-pilot/`
- `artifacts/indexes/dense-pilot/manifest.json`
- `artifacts/task_b_pilot_validation.json`
- `artifacts/task_b_search_example.json`
- `artifacts/runs/dense-custom-pilot/manifest.json`

Tests cover the original BM25 behavior plus masked pooling, padding invariance with real E5, query/passage prefixes, truncation, normalization, malformed vectors, checkpoint interruption/resume equivalence with deterministic fixture vectors, corrupt shards, exact cosine ordering/ties, overwrite protection, incomplete encodings, explicit pilot controls, model configuration identity, the 20-query structure, notebook cell syntax, a mocked-download execution of its source-relocation cell with real document lookup, and the Pyserini-free import path. The Colab route remains an unexecuted alternative; the actual Kaggle CUDA run and returned full index have now been verified.

## The required custom query suite

`annotations/custom_queries.draft.jsonl` contains 20 drafts, five per primary category: vocabulary mismatch, negation, homonyms/word sense, and temporal conditions. Every query has inclusion/exclusion rules and a 0–2 relevance rubric. Temporal cases specify concrete inclusive event-date intervals instead of ambiguous “right after” wording or unavailable publication dates.

Examples concern technology layoffs described indirectly; Social Security reserve depletion; football-related cognitive damage; Seattle employment findings with negation; court decisions opposing marriage bans; cricket as food versus the sport; Apple/FBI device access; jaguar conservation; and news events within explicit post-event windows.

Queries were written before the preliminary BM25 run. All 20 retrieved candidates in the corpus, but retrieval itself does not prove that hard-constraint-satisfying relevant articles exist. The saved BM25 run provides 20 candidates per question for corpus inspection, not gold labels or a test-set selection rule. No draft was removed because BM25 retrieved a poor result.

The blank `annotations/query_review.csv` is for the group's actual reviewer decisions. No human review, annotation agreement, nDCG@5, or MAP values have been invented. Freeze reviewed queries before the final comparison and pool equal-depth candidates from both **full-corpus** engines. Do not use the dense pilot as the neural side of the primary comparison. The existing 57-query qrels are not reusable labels for the new custom needs.

## Colab handoff

Files ready:

- `notebooks/News_IR_Dense_Encoding.ipynb`
- `artifacts/bundles/news_ir_colab.zip` (about 34 MB)
- `reports/COLAB_SETUP.md`

The bundle includes implementation source, the compact document-offset metadata, exact source/model identity, and the query drafts. It excludes raw articles, model weights, and the BM25 Lucene index. The notebook downloads the large public files directly and verifies their hashes. It uses a dedicated Drive folder for resumable checkpoints, builds the full index, exports draft query rankings, and produces a return archive.

Colab has a free tier with limited, unguaranteed GPU access. The notebook stops if no GPU is allocated; it does not silently start the full job on CPU or use anti-idle techniques. Trying the free tier does not require purchasing a plan. See the [official Colab FAQ](https://research.google.com/colaboratory/faq.html).

The user must open the notebook, choose a GPU, run its cells, grant Drive access if using persistent checkpoints, and return the resulting archive. This account-side execution has not been performed from this workspace. The equivalent Kaggle archive has since arrived and passed full coverage, ID, hash, local-search and ranking validation. Task B's full-corpus computation is complete.

## Remaining work

Full encoding and local integration are complete. The next dependency is actual group review and freezing of the query suite, followed by balanced pooling, human judgments, nDCG@5/MAP@1000, the comparison demo and the evidence-based research report. Both full engines now have verified depth-1,000 draft exports. Original source datasets and Task A artifacts are preserved.

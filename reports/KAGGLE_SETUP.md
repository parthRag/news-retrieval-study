# Run the full news encoder on Kaggle

Use your free Kaggle account's available GPU quota. This notebook needs **no Kaggle API credentials, Hugging Face token, OpenAI key, or paid model API**. If Kaggle asks you to verify your account before enabling accelerators, complete that in Kaggle. The GPU options and remaining quota shown in your account determine what is available; this guide does not assume a fixed weekly allocation or guarantee a session length.

## Files already prepared on your Mac

| File | Purpose |
| --- | --- |
| `notebooks/News_IR_Kaggle_Encoding.ipynb` | Import this notebook into Kaggle. |
| `artifacts/bundles/news_ir_kaggle.zip` | Upload this approximately 34 MB bundle as a **private** Kaggle Dataset. |
| `scripts/run_kaggle_dense.py` | Actual job driver, also included inside the bundle. |

The bundle contains the project code, compact document lookup metadata, model identity, and 20 draft queries. It excludes the corpus, model weights, and Lucene binaries. The notebook downloads the public corpus directly and verifies it against the complete SHA-256 of the local BM25 source. You do not need to upload the 2.45 GB corpus or set up GitHub.

## First run: exact steps

1. Sign in at [Kaggle](https://www.kaggle.com/). Keep your project Dataset and notebook private.
2. Open **Datasets → New Dataset** (or **Create → New Dataset**), upload `artifacts/bundles/news_ir_kaggle.zip`, name it `news-ir-gpu-input`, choose **Private**, and create it. Kaggle may automatically unpack the ZIP; the notebook supports both forms. Do not upload the original proposal or the complete project folder.
3. Create a notebook at [Kaggle Code](https://www.kaggle.com/code). Use **File → Import Notebook** (the import/upload option in the editor) and select `notebooks/News_IR_Kaggle_Encoding.ipynb` from your Mac. Import the actual `.ipynb`, not the ZIP.
4. In the notebook's **Add Input** panel, attach your `news-ir-gpu-input` Dataset. It should appear under `/kaggle/input/`. This is how the job finds the code and metadata.
5. Under **Settings → Accelerator**, choose **GPU T4 x2** when available. The implementation uses **one GPU**, `cuda:0`, even if two are offered. Enable **Internet** so packages, corpus and model can download. NVIDIA's [Kaggle setup instructions](https://docs.nvidia.com/datascience/deployment/26.10/platforms/kaggle/index.html) show the accelerator menu and note that GPU sessions consume quota. The first setup cell runs an actual CUDA operation to check compatibility before encoding.
6. In the first code cell, leave `BATCH_SIZE = 32` and `RESUME_ARCHIVE = None`. Set `TIME_BUDGET_HOURS` below your remaining session and quota allowance, with extra time reserved for downloads, installation, indexing and saving outputs. The default **6 hours applies to encoding only**, is checked after each completed shard, and is not a hard total-runtime cap. A smaller budget such as `2` works and will export a resumable checkpoint if encoding is unfinished.
7. Choose **Save Version → Save & Run All** to run the notebook once in a saved background session. Monitor its logs. Do not first run the entire job interactively and then start another Save & Run All: that launches another execution. If the editor already started an unused interactive GPU session, stop it before launching the saved run to avoid consuming quota twice. Menu wording can vary; choose the action that executes the notebook and saves its outputs when done.
8. Open the completed version's **Output** tab. Read `job_summary.json`. If `completed` is `true`, download **`dense-results.zip`** and **`job_summary.json`**. Otherwise, download/save **`dense-checkpoints.zip`**, then resume using the next section. A clean timed stop exits successfully with checkpoint output; it is not a final search index.
9. Stop any remaining GPU session when finished. Retain the saved checkpoint until the returned index has been verified locally.

Kaggle's Dataset upload options are described in its [Dataset documentation](https://www.kaggle.com/docs/datasets). Its [Notebook documentation](https://www.kaggle.com/docs/notebooks) describes notebook inputs, saved versions and outputs. GPU availability, quota and UI labels can change; the account's current UI is authoritative.

## What happens automatically

The driver checks CUDA before doing the encoding work. It downloads and verifies the exact source corpus and the tested E5-base-v2 revision `f52bf8ec8c7124536f0efb74aca902b2995e5bcd`, then runs a 128-document throughput benchmark. This gives an estimate for the GPU actually allocated; full-run time has not yet been measured on Kaggle.

Dependencies are installed in a separate environment under `/kaggle/temp`, avoiding conflicts with Kaggle's preinstalled vision/audio/data packages. PyTorch uses the official **2.9.1 CUDA 12.6** wheel, listed in [PyTorch's installation instructions](https://pytorch.org/get-started/previous-versions/), rather than choosing an arbitrary latest CUDA build. Transformers and Hugging Face Hub match the tested local versions. The cloud PyTorch/CUDA runtime differs from the Mac runtime and is recorded per shard; cloud execution still needs validation on the allocated hardware.

The setup creates the environment with `venv --without-pip`, then installs pip inside it using PyPA's official `get-pip.py`. This avoids the `ensurepip` failure reported on the hosted Python 3.13 image. See [pip's supported installation methods](https://pip.pypa.io/en/stable/installation/). If you already imported the older notebook, replace only its dependency-setup cell with the updated cell from `notebooks/News_IR_Kaggle_Encoding.ipynb`. Keep the configuration cell and attached Dataset; neither the job driver nor the upload bundle needs replacing for this fix. Internet must be enabled.

The full target is **594,589 eligible news articles**, matching BM25. Documents use title plus body, E5's `passage: ` prefix, a 512-token total input budget, masked mean pooling, float32 vectors and L2 normalization. Each complete 2,048-document shard is saved with ordered IDs, offsets and hashes. Once complete, the driver validates the complete document order, builds exact FAISS cosine search, and exports top-1,000 rankings for the 20 draft queries.

Temporary code, model and corpus downloads go under `/kaggle/temp/news_ir_task_b`; they can be recreated. Checkpoints, indexes and exports go under **`/kaggle/working`**, which is the output to save with the notebook version. Expect roughly **7 GiB** of working output for full shards, full index and both archives, plus temporary download space. The final result ZIP and full checkpoint ZIP are each about **1.7 GiB**. Do not depend on a still-running interactive session as your only copy.

Progress is logged after every shard. A time budget preserves the **full** target while reporting `completed: false` until every eligible document is encoded. The driver never substitutes a small pilot for the experiment. On completion, `job_summary.json` should show:

```json
{
  "completed": true,
  "encoded_documents": 594589,
  "target_documents": 594589,
  "coverage": "full",
  "query_count": 20,
  "total_hits": 20000
}
```

This is an excerpt of the expected schema, **not a claim that the cloud run has already completed**. `coverage: full` describes the selected corpus; always also check `completed` and the actual encoded count.

## Resume after a timed stop

1. Keep the successful saved version containing `dense-checkpoints.zip`.
2. Create another GPU notebook from the same provided notebook. Attach the original private project Dataset and the previous notebook's saved output through **Add Input**. Alternatively download the checkpoint ZIP and upload it as another private Dataset, then attach that. Both intact ZIPs and automatically extracted checkpoint directories are supported.
3. Copy the checkpoint file's actual `/kaggle/input/.../dense-checkpoints.zip` path from the input file browser. Set:

   ```python
   RESUME_ARCHIVE = "/kaggle/input/your-previous-output/dense-checkpoints.zip"
   ```

   If Kaggle extracted the ZIP, point `RESUME_ARCHIVE` at the directory containing `encodings/` instead. The input file browser shows the actual path; do not guess it.

4. Enable Internet and GPU, adjust the budget to the remaining allowance, and use **Save Version → Save & Run All** again. The job verifies and restores committed shards to writable working storage, then continues from their source offsets. Model, corpus, document count and shard size must match. You may reduce the batch size to `16` or `8` after an out-of-memory error.
5. Repeat until `completed` is true and `dense-results.zip` is present.

A hard session termination can lose files that have not been saved in notebook outputs. The timed stop is designed to finish normally and export checkpoints before that happens, but cannot prevent a provider interruption. It can run one shard beyond its encoding budget, plus finalization time. Keep the budget conservative. If a cell errors, read the traceback; a partial checkpoint alone does not mean the final index exists.

## Bring the final index back

Put `dense-results.zip` in `/Users/parthraghuvanshi/Desktop/IR`. In a terminal opened in that project directory:

```sh
unzip -n dense-results.zip -d artifacts
.venv/bin/news-ir dense-search "cricket insect lifecycle" --top-k 5
```

The archive contains `indexes/dense/`, `runs/dense-custom-draft/` and `gpu_benchmark_kaggle.json`. Local CLI defaults supply your existing Mac model and BM25 document metadata instead of the temporary Kaggle paths. Existing files are not overwritten by the extraction command.

Return `job_summary.json` with the ZIP so we can verify the complete index and integrate it into the demo. The next research work is reviewing/freezing the queries, pooling full-corpus results from both engines, collecting human relevance judgments, calculating nDCG@5 and MAP, and writing the failure analysis/report. Draft rankings do not supply those labels or metrics.

## Rebuild after source changes

The bundle has already been built. If we change the project code before uploading, regenerate it from the Mac project root:

```sh
.venv/bin/python scripts/prepare_kaggle_bundle.py
```

The resulting file identity is recorded in `artifacts/kaggle_bundle_manifest.json`. Local tests validate handoff behavior and resume integrity; actual Kaggle CUDA speed and successful output saving require the real cloud run.

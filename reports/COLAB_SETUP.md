# Run the complete E5 encoding job in Colab

Colab has a free tier. Free GPU allocation, GPU type, and session lifetime are not guaranteed, so try it before considering a paid plan. See [Google's FAQ](https://research.google.com/colaboratory/faq.html). This project uses a normal notebook, with no anti-idle or quota-bypass code.

## Setup

1. Open [Google Colab](https://colab.research.google.com/) and sign in with your Google account.
2. Choose **Upload notebook** and select `notebooks/News_IR_Dense_Encoding.ipynb` from this project.
3. Choose **Runtime → Change runtime type → GPU**, then connect. If Colab offers a T4, it is a suitable starting point. The first cell checks that a GPU was actually allocated.
4. Run the cells in order using each cell's play button. In the bundle-upload cell, select `artifacts/bundles/news_ir_colab.zip` (about 34 MB). You do not need to upload the 2.45 GB corpus through the browser.
5. Allow Google Drive access when prompted so the notebook can save checkpoints in `MyDrive/IR_Project/`. Keep about 6 GB free there for the encoding shards, index, and result archive.
6. Inspect the GPU benchmark estimate, then run the full-encoding cell. Runtime depends on the GPU actually assigned. Checkpoint messages show progress; do not start a second session on the same checkpoint folder.

Setup is a few notebook actions, followed by automatic package/model/corpus downloads. Download/install time and full encoding take longer than opening the notebook. No OpenAI API key or model training is needed.

## What the notebook does

- Downloads the same corpus mirror and verifies its complete SHA-256 against the existing BM25 corpus.
- Downloads the exact tested E5-base-v2 revision and verifies its model/tokenizer hashes.
- Uses the same 594,589 eligible documents as BM25, in the same source order.
- Encodes title plus body within the 512-token model input budget using E5's query/passage prefixes, masked mean pooling, and normalized float32 vectors.
- Saves complete shards to Drive. A resumed session verifies finished shards and continues after their source offsets.
- Builds an exact FAISS cosine index and exports rankings for the 20 draft queries.
- Produces `dense-results.zip` in the Drive job folder.

The notebook contains the actual implementation used by the local pilot, rather than a separate approximation. Encoding and vector search do not require Java or the BM25 index files inside Colab; the bundle includes only the compact source lookup metadata.

## If a session disconnects

Reconnect to a GPU, repeat the setup/download/mount cells, and run the encoding cell again. It adds `--resume` when it finds the existing configuration. If GPU memory is insufficient, reduce `BATCH_SIZE` from 32 to 16 or 8; committed shards remain usable. Changing model identity, corpus, shard size, or the selected document count is rejected rather than silently mixing jobs.

Drive checkpoints are the persistent output. Files under `/content` may disappear between sessions and can be downloaded again. If Google cannot allocate a free GPU, that is a resource limitation; the notebook will stop rather than silently run the corpus on CPU.

## Return the results

Open Google Drive → **IR_Project** → the job folder printed by the notebook. Download **dense-results.zip** through Drive and place it in `/Users/parthraghuvanshi/Desktop/IR`.

From the project root, the archive can be extracted without overwriting existing files:

```sh
unzip -n dense-results.zip -d artifacts
```

Then full-corpus dense search will use the local BM25 document metadata and local tested model:

```sh
.venv/bin/news-ir dense-search "cricket insect lifecycle" --top-k 5
```

Keep the Drive checkpoints until the local full index and query run have been verified. The current local `dense-pilot` index has only 512 articles and cannot substitute for this full-corpus result. Neither the notebook nor the pilot creates human relevance judgments; those are still needed for nDCG@5 and MAP.

# GitHub repositories and submission handoff

**Public final-submission repository:** https://github.com/parthRag/news-ir-bm25-dense-final

**Private development repository:** https://github.com/parthRag/news-ir-bm25-dense

The original repository and its development history are retained privately. The public repository publishes a clearly labeled final snapshot, including active implementation code, preprocessing scripts, notebooks, final PDFs, current assessment-method documentation, frozen judgment records, saved rankings and evaluation evidence. Its import commits record snapshot publication; they do not represent a reconstructed development history.

The four-page report links to the public final repository. `configs/submission.json` records this public URL and the private development repository separately. `artifacts/github_publication.json` records the public repository's initial publication and visibility.

The public snapshot is exported from the validated reproducibility package. Its root `PACKAGE_MANIFEST.json` binds the exported files, so numerical checks can run directly from a source checkout without downloading the large corpus or model. `deliverables/final_validation.json` is a generated verification result. The GitHub release also provides the complete ZIP, PDFs and outer release manifest. Corpus text, full-article assessment packets, model weights, encodings and built indexes remain excluded; they must be restored for article lookup and live search.

Continue development in the private working repository. To update the public submission, regenerate and validate the PDFs and package, export a new labeled snapshot, then publish that snapshot and its release together. Avoid pushing the private development branch directly to the public snapshot repository.

Component responsibilities and actual individual contribution confirmations remain separate; see `CONTRIBUTING.md`. The preliminary-reference method and planned human-review stage remain in `reports/ASSESSMENT_METHOD.md`.

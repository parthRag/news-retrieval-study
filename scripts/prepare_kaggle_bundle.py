"""Build the private Kaggle input upload from the tested project implementation."""

import json
from pathlib import Path

from prepare_colab_bundle import prepare_bundle


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    info = prepare_bundle(root / "artifacts/bundles/news_ir_kaggle.zip",
                          extra_files=("scripts/run_kaggle_dense.py",))
    (root / "artifacts/kaggle_bundle_manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))

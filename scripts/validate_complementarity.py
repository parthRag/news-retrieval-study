"""Recompute diagnostics and independently check candidate-union ceilings/recall."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import ir_measures

from news_ir.data import sha256_file
from news_ir.diagnostics import DEPTHS
from analyze_complementarity import ROOT, analyze, load_inputs, write


def validate(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        if sha256_file(folder / name) != digest:
            raise ValueError("Diagnostic output changed: " + name)
    for name, digest in {**manifest["inputs"], **manifest["code"]}.items():
        if sha256_file(ROOT / name) != digest:
            raise ValueError("Diagnostic source changed: " + name)
    # Portable mode deliberately does not require corpus/models/indexes.
    scopes, raw, inputs, _, _ = load_inputs()
    if inputs != manifest["inputs"]:
        raise ValueError("Input set changed")
    outputs = analyze(scopes, raw, samples=manifest["samples"], seed=manifest["seed"])
    for name, result in zip(("summary.json", "per_query.json", "paired_comparisons.json",
                             "formulation_stability.json", "checks.json"), outputs, strict=True):
        if result != json.loads((folder / name).read_text(encoding="utf-8")):
            raise ValueError("Diagnostic recomputation differs: " + name)
    details = outputs[1]
    comparisons, maximum = 0, 0.0
    for name, scope in scopes.items():
        evaluator = ir_measures.evaluator([ir_measures.nDCG @ 5, ir_measures.R @ 2000], scope["qrels"])
        for depth in DEPTHS:
            oracles = {}
            for q, labels in scope["qrels"].items():
                union = set(scope["runs"]["bm25"][q][:depth]) | set(scope["runs"]["dense"][q][:depth])
                ordered = sorted(union, key=lambda d: (-labels.get(d, 0), d))
                oracles[q] = {d: len(ordered) - i for i, d in enumerate(ordered)}
            for item in evaluator.iter_calc(oracles):
                field = "oracle_union_ndcg_at_5" if str(item.measure) == "nDCG@5" else "union_recall"
                expected = details[name][item.query_id]["depths"][str(depth)][field]
                difference = abs(expected - item.value)
                if difference > 1e-12:
                    raise ValueError(f"Independent oracle/recall disagreement: {name}/{item.query_id}/{depth}/{field}")
                comparisons += 1
                maximum = max(maximum, difference)
    expected_count = sum(len(s["qrels"]) for s in scopes.values()) * len(DEPTHS) * 2
    if comparisons != expected_count:
        raise ValueError("Independent evaluator omitted a topic/metric")
    # A source must still have the same bytes after validation.
    for name, digest in manifest["inputs"].items():
        if sha256_file(ROOT / name) != digest:
            raise ValueError("An input changed during validation: " + name)
    return {"status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "diagnostic_manifest_sha256": sha256_file(folder / "manifest.json"),
            "recomputed_outputs": 5, "input_files_verified": len(inputs),
            "independent_backend": "ir_measures " + ir_measures.__version__,
            "independent_candidate_oracle_and_recall_values": comparisons,
            "max_independent_absolute_difference": maximum,
            "checks": outputs[4],
            "scope": "Portable numerical reproduction; no new labels or corpus-wide coverage assertion",
            "validator_sha256": sha256_file(Path(__file__))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "artifacts/evaluations/complementarity-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/complementarity-validation/numerical.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Validation output exists; choose a new path")
    result = validate(args.input.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

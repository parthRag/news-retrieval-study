"""Assemble unchanged source runs, validate assessments, and evaluate all 40.

Run with --prepare-only while assessment is in progress. Completed evaluation
requires every candidate in both designated top-20 pools to have a valid label.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from news_ir.assessment import prepare_pool, validate_assessments, write_jsonl
from news_ir.custom_depth20 import evaluate_depth20_study
from news_ir.data import DocumentStore, sha256_file
from news_ir.evaluation import load_run
from news_ir.expanded_study import clustered_comparison, join_saved_runs

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "annotations/custom40_v2"
NEW_POOL = ROOT / "artifacts/assessments/custom40-extension20-v2"
ALL_POOL = ROOT / "artifacts/assessments/custom40-v2"


def read(path):
    return json.loads(path.read_text())


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def prepare():
    protocol = read(DESIGN / "protocol.json")
    for name, digest in protocol["files"].items():
        if sha256_file(DESIGN / name) != digest:
            raise ValueError("Frozen query design changed")
    with DocumentStore(ROOT / "artifacts/indexes/bm25") as store:
        eligible = {r[0] for r in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
        corpus = store.manifest["source"]["sha256"]
    paths = {}
    for engine, original in [("bm25", "bm25-custom-draft-depth1000"), ("dense", "dense-custom-draft")]:
        output = ROOT / f"artifacts/runs/{engine}-custom40-v2"
        components = [(ROOT / "annotations/ai_study_v1/queries.jsonl", ROOT / "artifacts/runs" / original),
                      (DESIGN / "queries.extension20.jsonl", ROOT / f"artifacts/runs/{engine}-custom40-extension20-v2")]
        if not output.exists():
            join_saved_runs(DESIGN / "queries.all40.jsonl", components,
                            ROOT / f"artifacts/indexes/{engine}", eligible, output)
        _, manifest = load_run(output, DESIGN / "queries.all40.jsonl", eligible, expected_source_sha256=corpus)
        if [c["manifest_sha256"] for c in manifest["components"]] != [sha256_file(p / "manifest.json") for _, p in components]:
            raise ValueError("Joined run uses different source components")
        paths[engine] = output
    if not ALL_POOL.exists():
        prepare_pool(queries_path=DESIGN / "queries.all40.jsonl", bm25_run=paths["bm25"], dense_run=paths["dense"],
                     document_index=ROOT / "artifacts/indexes/bm25", output=ALL_POOL, depth=20)
    combined = {(r["query_id"], r["doc_id"]): r for r in records(ALL_POOL / "articles.blinded.jsonl")}
    expected = {}
    for pool in [ROOT / "artifacts/assessments/custom20-v1", NEW_POOL]:
        for row in records(pool / "articles.blinded.jsonl"):
            key = row["query_id"], row["doc_id"]
            if key in expected:
                raise ValueError("Original and extension query pools overlap")
            expected[key] = row
    if combined != expected or len(combined) != 1444:
        raise ValueError("Combined pool differs from the exact two frozen source pools")
    for name, digest in read(ALL_POOL / "protocol.json")["files"].items():
        if sha256_file(ALL_POOL / name) != digest:
            raise ValueError("Combined pool file changed")
    return {"status": "prepared", "combined_pairs": len(combined), "query_count": 40,
            "retrieval": "Source ranks and scores preserved; no new retrieval or timing measurement"}


def merge_assessments():
    category_names = {"vocabulary": "vocabulary_mismatch", "negation": "negation", "homonym": "homonym", "temporal": "temporal"}
    queries = {q["_id"]: q for q in records(DESIGN / "queries.extension20.jsonl")}
    articles = records(NEW_POOL / "articles.blinded.jsonl")
    lookup, part_sources = {}, {}
    for name, category in category_names.items():
        path = DESIGN / f"assessments.{name}.jsonl"
        validation = validate_assessments(NEW_POOL, path)
        rows = records(path)
        expected = {(a["query_id"], a["doc_id"]) for a in articles if queries[a["query_id"]]["category"] == category}
        if {(r["query_id"], r["doc_id"]) for r in rows} != expected:
            raise ValueError("Category assessment coverage incomplete: " + name)
        for row in rows:
            key = row["query_id"], row["doc_id"]
            if key in lookup:
                raise ValueError("Overlapping assessor assignments")
            lookup[key] = row
        part_sources[path.name] = {"sha256": sha256_file(path), "pairs": validation["assessed_pairs"]}
    audit = read(DESIGN / "adjudication.json")
    for decision in audit["decisions"]:
        key = decision["query_id"], decision["doc_id"]
        initial = lookup[key]
        if initial["grade"] != decision["original_grade"]:
            raise ValueError("Audit initial grade differs from assessor source")
        if decision["final_grade"] != initial["grade"]:
            revised = dict(initial)
            revised.update(grade=decision["final_grade"], rationale=decision["reason"],
                           adjudication={"original_grade": initial["grade"], "source": "adjudication.json"})
            lookup[key] = revised
    ordered = [lookup[(a["query_id"], a["doc_id"])] for a in articles]
    destination = DESIGN / "assessments.extension20.jsonl"
    if destination.exists():
        old = records(destination)
        if any(lookup.get((r["query_id"], r["doc_id"])) != r for r in old):
            raise ValueError("An earlier extension decision was changed")
    temporary = destination.with_suffix(".merging.jsonl")
    write_jsonl(temporary, ordered)
    validation = validate_assessments(NEW_POOL, temporary)
    if not validation["complete_pool"]:
        raise ValueError("Extension pool incomplete")
    temporary.replace(destination)
    original = ROOT / "annotations/ai_study_v1/assessments.depth20.jsonl"
    design = read(DESIGN / "protocol.json")
    if sha256_file(original) != design["original_assessments_sha256"]:
        raise ValueError("Original 737 decisions changed")
    combined = DESIGN / "assessments.all40.jsonl"
    combined.write_bytes(original.read_bytes() + destination.read_bytes())
    all_validation = validate_assessments(ALL_POOL, combined)
    if not all_validation["complete_pool"]:
        raise ValueError("Combined 40-query pool incomplete")
    for pool, source, name in [(NEW_POOL, destination, "extension20"), (ALL_POOL, combined, "all40")]:
        top5 = {(r["query_id"], r["doc_id"]) for r in records(pool / "pool.provenance.jsonl") if r["priority_top5"]}
        write_jsonl(DESIGN / f"assessments.{name}.top5.jsonl", [r for r in records(source) if (r["query_id"], r["doc_id"]) in top5])
    result = {"status": "complete", "assessor_type": "AI", "extension_pairs": len(ordered),
              "combined_pairs": all_validation["assessed_pairs"], "original_records_preserved": 737,
              "parallel_category_sources": part_sources,
              "adjudication_sha256": sha256_file(DESIGN / "adjudication.json"),
              "extension_grade_distribution": dict(Counter(r["grade"] for r in ordered)),
              "extension_confidence_distribution": dict(Counter(r["confidence"] for r in ordered)),
              "top5_snapshot_timing": "Derived at complete-pool integration; not a separate earlier pilot",
              "design_protocol_sha256": sha256_file(DESIGN / "protocol.json"),
              "assessments_extension_sha256": sha256_file(destination), "assessments_all40_sha256": sha256_file(combined)}
    write(DESIGN / "assessment_completion.json", result)
    return result


def evaluate():
    for pool, source, seed, name in [
        (NEW_POOL, "extension20", "extension20", "custom40-extension20-depth20-v2"),
        (ALL_POOL, "all40", "all40", "custom40-depth20-v2")]:
        output = ROOT / "artifacts/evaluations" / name
        if output.exists():
            raise FileExistsError("Evaluation already exists; retain it and choose a new version")
        result = evaluate_depth20_study(pool, DESIGN / f"assessments.{source}.jsonl",
                                       DESIGN / f"assessments.{seed}.top5.jsonl",
                                       ROOT / "artifacts/indexes/bm25", output)
        print(json.dumps({"evaluation": name, "comparisons": result["independent_metric_comparisons"],
                          "aggregate": result["aggregate"]}, indent=2))
    output = ROOT / "artifacts/evaluations/custom40-depth20-v2"
    primary = read(output / "metrics.json")["linear"]
    families = read(DESIGN / "topic_families.json")
    conservative = dict(families)
    conservative.update(N02="marriage_law", T03="marriage_law", N03="ebola", T04="ebola")
    clustered = {"design_families": clustered_comparison(primary["bm25"], primary["dense"], families),
                 "broader_topic_sensitivity": clustered_comparison(primary["bm25"], primary["dense"], conservative)}
    write(output / "clustered_comparison.json", clustered)
    manifest = read(output / "manifest.json")
    manifest["files"]["clustered_comparison.json"] = sha256_file(output / "clustered_comparison.json")
    write(output / "manifest.json", manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(), indent=2))
    if not args.prepare_only:
        print(json.dumps(merge_assessments(), indent=2))
        evaluate()

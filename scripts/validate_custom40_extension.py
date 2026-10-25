"""Check the frozen extension, saved rankings and full-text candidate pool.

This validates retrieval provenance and coverage; it does not assign relevance.
"""
import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from news_ir.assessment import text_hash
from news_ir.data import DocumentStore, read_queries, sha256_file
from news_ir.evaluation import load_run

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "annotations/custom40_v2"
POOL = ROOT / "artifacts/assessments/custom40-extension20-v2"


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    protocol = read(DESIGN / "protocol.json")
    for name, digest in protocol["files"].items():
        require(sha256_file(DESIGN / name) == digest, "Changed frozen design file: " + name)
    original = ROOT / protocol["original_queries"]["path"]
    require(sha256_file(original) == protocol["original_queries"]["sha256"], "Original queries changed")
    require(sha256_file(ROOT / "annotations/ai_study_v1/assessments.depth20.jsonl") ==
            protocol["original_assessments_sha256"], "Original assessments changed")
    new_path = DESIGN / "queries.extension20.jsonl"
    combined_path = DESIGN / "queries.all40.jsonl"
    require(combined_path.read_bytes() == original.read_bytes() + new_path.read_bytes(),
            "Combined suite must preserve exact original bytes")
    new = [json.loads(line) for line in new_path.read_text().splitlines()]
    combined = [json.loads(line) for line in combined_path.read_text().splitlines()]
    require(len(read_queries(combined_path)) == 40, "Expected 40 unique query IDs")
    require(len({r["text"] for r in combined}) == 40, "Repeated query text")
    require(Counter(r["category"] for r in new) ==
            dict.fromkeys(protocol["category_counts"], 5), "Expected five new queries per category")
    require(Counter(r["category"] for r in combined) == protocol["category_counts"], "Category imbalance")
    for row in new:
        require(all(row.get(k) for k in ["relevant_if", "exclude_if", "grade_0", "grade_1", "grade_2"]),
                "Missing relevance rubric")
        if row["category"] == "temporal":
            window = row["event_window"]
            anchor = date.fromisoformat(window["anchor_date"])
            require(date.fromisoformat(window["start_inclusive"]) == anchor + timedelta(days=1),
                    "Incorrect temporal start")
            require(date.fromisoformat(window["end_inclusive"]) ==
                    anchor + timedelta(days=window["days_after_anchor"]), "Incorrect temporal end")
            require(row["anchor_source_url"].startswith("https://"), "Missing anchor source")
    families = read(DESIGN / "topic_families.json")
    require(set(families) == {r["_id"] for r in combined}, "Family mapping must cover every query")
    require(len(set(families.values())) == protocol["analysis_plan"]["topic_families"], "Family count")
    pool_protocol = read(POOL / "protocol.json")
    for name, digest in pool_protocol["files"].items():
        require(sha256_file(POOL / name) == digest, "Pool file changed: " + name)
    require((POOL / "queries.jsonl").read_bytes() == new_path.read_bytes(), "Pool queries differ")
    runs = {}
    with DocumentStore(ROOT / "artifacts/indexes/bm25") as store:
        eligible = {r[0] for r in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
        for engine in ["bm25", "dense"]:
            folder = ROOT / f"artifacts/runs/{engine}-custom40-extension20-v2"
            rankings, manifest = load_run(folder, new_path, eligible,
                                         expected_source_sha256=store.manifest["source"]["sha256"])
            require(manifest["query_count"] == 20 and manifest["total_hits"] == 20000,
                    "Incomplete extension run")
            require(datetime.fromisoformat(protocol["created_at_utc"]) <
                    datetime.fromisoformat(manifest["created_at_utc"]), "Design was not frozen before run")
            require(pool_protocol["runs"][engine]["manifest_sha256"] == sha256_file(folder / "manifest.json"),
                    "Pool/run lineage differs")
            runs[engine] = rankings
        expected = {(q["_id"], doc) for q in new for run in runs.values() for doc in run[q["_id"]][:20]}
        expected_top5 = {(q["_id"], doc) for q in new for run in runs.values() for doc in run[q["_id"]][:5]}
        articles = [json.loads(line) for line in (POOL / "articles.blinded.jsonl").read_text().splitlines()]
        require(len(articles) == len(expected), "Duplicate or missing pool articles")
        require({(r["query_id"], r["doc_id"]) for r in articles} == expected, "Asymmetric candidate pool")
        for article in articles:
            doc = store.get(article["doc_id"])
            require(doc is not None and doc.eligible and doc.title == article["title"] and
                    doc.text == article["text"] and text_hash(doc.contents) == article["contents_sha256"],
                    "Article packet differs from corpus")
    provenance = [json.loads(line) for line in (POOL / "pool.provenance.jsonl").read_text().splitlines()]
    require(len(provenance) == len(expected), "Provenance count mismatch")
    require({(r["query_id"], r["doc_id"]) for r in provenance} == expected, "Provenance membership mismatch")
    for row in provenance:
        qid, doc = row["query_id"], row["doc_id"]
        require(row["priority_top5"] == ((qid, doc) in expected_top5), "Top-five priority mismatch")
        require(row["component_ranks"] == {e: ranks[qid].index(doc) + 1 for e, ranks in runs.items()
                                          if doc in ranks[qid][:20]}, "Incorrect component ranks")
    result = {"status": "passed", "combined_query_count": 40, "extension_query_count": 20,
              "category_counts": protocol["category_counts"], "retrieved_hits_per_engine": 20000,
              "extension_pooled_pairs": len(expected), "extension_priority_top5_pairs": len(expected_top5),
              "extension_pool_counts_by_query": dict(sorted(Counter(qid for qid, _ in expected).items())),
              "extension_assessment_status": "complete" if (DESIGN / "assessment_completion.json").exists() else "pending",
              "original20_queries_and_737_assessments": "byte-identical",
              "design_protocol_sha256": sha256_file(DESIGN / "protocol.json"),
              "pool_protocol_sha256": sha256_file(POOL / "protocol.json")}
    (ROOT / "artifacts/custom40_extension_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

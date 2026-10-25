"""Evidence-backed AI assessments, kept separate from the supplied TREC qrels."""

import hashlib
import json
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .data import DocumentStore, read_queries, sha256_file
from .evaluation import load_run


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def prepare_pool(*, queries_path, bm25_run, dense_run, document_index, output, depth=20):
    """Freeze exact query bytes and export full articles without ranker metadata.

    The source's historical draft status is preserved for hash compatibility;
    the new protocol records authorization for AI assessment and the freeze.
    """
    if type(depth) is not int or not 5 <= depth <= 1000:
        raise ValueError("Pool depth must be an integer in 5..1000")
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError("Assessment pool exists; choose a new version")
    queries = read_queries(queries_path)
    records = [json.loads(line) for line in Path(queries_path).read_text().splitlines()]
    for record in records:
        if any(not record.get(key) for key in ("category", "relevant_if", "exclude_if", "grade_0", "grade_1", "grade_2")):
            raise ValueError("Each query needs category, inclusion/exclusion rules and a grading rubric")
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.pooling-", dir=target.parent))
    try:
        with DocumentStore(document_index) as store:
            source_hash = store.manifest["source"]["sha256"]
            eligible = {row[0] for row in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
            runs = {}
            for name, path, expected in (("bm25", bm25_run, "lucene-bm25"), ("dense", dense_run, "e5-cosine")):
                rankings, manifest = load_run(path, queries_path, eligible, expected_source_sha256=source_hash)
                if manifest["engine"] != expected:
                    raise ValueError("Assessment component engines are swapped or incorrect")
                runs[name] = (rankings, manifest, Path(path))
            packets, private = [], []
            for query in queries:
                qid = query["_id"]
                ids = {doc for rankings, _, _ in runs.values() for doc in rankings[qid][:depth]}
                priority = {doc for rankings, _, _ in runs.values() for doc in rankings[qid][:5]}
                # Deterministic shuffled order does not reveal which ranker retrieved an article.
                for doc_id in sorted(ids, key=lambda doc: text_hash(qid + "\0" + doc)):
                    doc = store.get(doc_id)
                    if doc is None or not doc.eligible:
                        raise ValueError("Pooled article unavailable or empty")
                    packets.append({"query_id": qid, "doc_id": doc_id, "title": doc.title, "text": doc.text,
                                    "contents_sha256": text_hash(doc.contents)})
                    private.append({"query_id": qid, "doc_id": doc_id, "priority_top5": doc_id in priority,
                                    "component_ranks": {name: rankings[qid].index(doc_id) + 1
                                                        for name, (rankings, _, _) in runs.items()
                                                        if doc_id in rankings[qid][:depth]}})
        shutil.copyfile(queries_path, working / "queries.jsonl")
        write_jsonl(working / "articles.blinded.jsonl", packets)
        write_jsonl(working / "pool.provenance.jsonl", private)
        protocol = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "frozen_for_ai_diagnostic_assessment", "assessor_type": "AI",
            "authorization": "User explicitly requested assistant document relevance judgments; human approval is not a prerequisite",
            "query_count": len(queries), "pool_depth_per_engine": depth,
            "pooled_pairs": len(packets), "priority_top5_pairs": sum(p["priority_top5"] for p in private),
            "category_counts": dict(Counter(r["category"] for r in records)),
            "corpus_sha256": source_hash, "eligible_documents": len(eligible),
            "query_source_sha256": sha256_file(queries_path),
            "historical_status": "Exact source query/rubric bytes and status fields are preserved. This protocol authorizes AI assessment; no human review is claimed.",
            "judgment_policy": {
                "grades": "0 irrelevant/constraint violation; 1 relevant limited detail; 2 directly relevant substantive evidence",
                "hard_constraints": "All mandatory inclusion constraints apply; omission alone is not proof of negation",
                "temporal": "Inclusive event windows; date must be supported in article text; publication dates unavailable",
                "mixed_articles": "An article may discuss opposing findings; judge whether it supplies the requested evidence, not whether every passage supports it",
                "uncertainty": "Leave unresolved candidates unassessed; do not silently turn uncertainty into grade 0",
                "evidence": "Read full title and body; retain exact quotations and Unicode character offsets into (title + newline + body).strip()",
                "blinding": "Article packets omit engine/rank/score. Assessor has seen some prior results; perfect blindness is not claimed.",
                "freeze_timing": "This pool protocol is generated after retrieval. Query-design timing and prior result exposure must be documented in the source study protocol; no preregistration is claimed here.",
                "independence": "AI diagnostic labels, not human gold. No independent inter-assessor agreement is claimed.",
            },
            "evaluation_policy": {
                "ndcg": "Linear 0–2 gains; report only for queries with complete top-five union judgments; ideal ranking uses assessed pool positives",
                "map": "MAP@1000 only after the designated pool is complete; shallow-pool estimate, unassessed != confirmed irrelevant",
                "pilot": "Partial query coverage must be explicit; never publish a partial pilot as an aggregate over the full query suite",
                "original_qrels": "Do not change or merge the original 57-query qrels",
            },
            "runs": {name: {"path": str(path.resolve()), "manifest_sha256": sha256_file(path / "manifest.json"),
                            "run_sha256": meta["run_sha256"]} for name, (_, meta, path) in runs.items()},
            "files": {p.name: sha256_file(p) for p in working.iterdir() if p.is_file()},
        }
        if sha256_file(queries_path) != protocol["query_source_sha256"]:
            raise ValueError("Query source changed while preparing pool")
        (working / "protocol.json").write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n")
        working.rename(target)
        return protocol
    except BaseException:
        shutil.rmtree(working)
        raise


def validate_assessments(pool_dir, assessments_path):
    """Check provenance, exact evidence spans, grade types and pool membership."""
    pool = Path(pool_dir)
    protocol = json.loads((pool / "protocol.json").read_text())
    for name, digest in protocol["files"].items():
        if sha256_file(pool / name) != digest:
            raise ValueError(f"Assessment pool hash mismatch: {name}")
    articles = {(r["query_id"], r["doc_id"]): r for r in
                map(json.loads, (pool / "articles.blinded.jsonl").read_text().splitlines())}
    priority = {(r["query_id"], r["doc_id"]) for r in
                map(json.loads, (pool / "pool.provenance.jsonl").read_text().splitlines()) if r["priority_top5"]}
    qrels, seen = {}, set()
    for row in map(json.loads, Path(assessments_path).read_text().splitlines()):
        pair = row.get("query_id"), row.get("doc_id")
        if pair in seen or pair not in articles:
            raise ValueError("Duplicate assessment or pair outside frozen pool")
        if type(row.get("grade")) is not int or row["grade"] not in (0, 1, 2):
            raise ValueError("AI assessment grade must be integer 0..2")
        if (row.get("assessor_type") != "AI" or row.get("full_article_read") is not True
                or row.get("confidence") not in {"low", "medium", "high"}
                or not isinstance(row.get("rationale"), str) or not row["rationale"].strip()
                or not row.get("assessed_at_utc") or not row.get("evidence")):
            raise ValueError("Missing AI disclosure, full-read acknowledgment, rationale, confidence, date or evidence")
        article = articles[pair]
        contents = (article["title"] + "\n" + article["text"]).strip()
        if row.get("contents_sha256") != text_hash(contents) or article["contents_sha256"] != text_hash(contents):
            raise ValueError("Assessment article hash mismatch")
        for span in row["evidence"]:
            start, end, quote = span.get("start"), span.get("end"), span.get("quote")
            if (type(start) is not int or type(end) is not int or not isinstance(quote, str)
                    or not 0 <= start < end <= len(contents) or contents[start:end] != quote):
                raise ValueError("Evidence quote/character offsets do not match source article")
        seen.add(pair)
        qrels.setdefault(pair[0], {})[pair[1]] = row["grade"]
    qids = [q["_id"] for q in read_queries(pool / "queries.jsonl")]
    complete_top5 = [qid for qid in qids if {p for p in priority if p[0] == qid} <= seen]
    return {"status": "passed", "assessor_type": "AI", "assessed_pairs": len(seen),
            "pooled_pairs": len(articles), "remaining_pairs": len(articles) - len(seen),
            "priority_top5_pairs": len(priority), "priority_top5_assessed": len(priority & seen),
            "complete_top5_query_ids": complete_top5,
            "complete_pool": len(seen) == len(articles), "qrels": qrels}


def assessed_top5_metrics(pool_dir, assessments_path):
    """Publish only top-five metrics for queries whose top-five union is assessed.

    This intentionally withholds MAP until the specified pool is complete.
    The ideal ranking uses known pool positives; deeper assessments may change it.
    """
    from .evaluation import evaluate_query

    pool = Path(pool_dir)
    validation = validate_assessments(pool, assessments_path)
    completed = validation["complete_top5_query_ids"]
    if not completed:
        raise ValueError("No query has a completely assessed top-five union")
    provenance = list(map(json.loads, (pool / "pool.provenance.jsonl").read_text().splitlines()))
    per_query, exp2_sensitivity = {}, {}
    for qid in completed:
        per_query[qid], exp2_sensitivity[qid] = {}, {}
        for engine in ("bm25", "dense"):
            ranked = sorted(((row["component_ranks"][engine], row["doc_id"]) for row in provenance
                             if row["query_id"] == qid and engine in row["component_ranks"]
                             and row["component_ranks"][engine] <= 5))
            metrics = evaluate_query([doc_id for _, doc_id in ranked], validation["qrels"].get(qid, {}))
            per_query[qid][engine] = {name: metrics[name] for name in ("ndcg_at_5", "precision_at_5", "judged_at_5")}
            exp2_sensitivity[qid][engine] = evaluate_query(
                [doc_id for _, doc_id in ranked], validation["qrels"].get(qid, {}), gain_mode="exp2")["ndcg_at_5"]
    qids = [q["_id"] for q in read_queries(pool / "queries.jsonl")]
    return {"scope": "AI-assessed top-five pilot; not the complete 20-query study", "assessor_type": "AI",
            "query_ids": completed, "query_count": len(completed), "suite_query_count": len(qids),
            "pending_query_ids": [qid for qid in qids if qid not in completed],
            "assessed_pairs": validation["assessed_pairs"], "pool_pairs": validation["pooled_pairs"],
            "per_query": per_query, "primary_gain": "linear grade 0–2",
            "exp2_gain_sensitivity_ndcg_at_5": exp2_sensitivity,
            "macro_over_completed_queries_only": {
                engine: {metric: sum(per_query[q][engine][metric] for q in completed) / len(completed)
                         for metric in ("ndcg_at_5", "precision_at_5", "judged_at_5")}
                for engine in ("bm25", "dense")},
            "map_status": "Withheld: the depth-20 pool is incomplete; no full-suite MAP claim",
            "limitations": "Linear gains 0–2; IDCG from assessed positives only and may change with deeper assessment. AI labels are not independent human gold. Top-five coverage does not establish corpus recall.",
            "protocol_sha256": sha256_file(pool / "protocol.json"),
            "assessments_sha256": sha256_file(assessments_path)}

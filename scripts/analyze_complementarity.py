"""Explain engine complementarity and fixed RRF using existing saved evidence.

No model training, encoding, retrieval, new judgments or parameter tuning. The
three benchmarks and their query formulations remain separate throughout.
"""
import argparse
import csv
import json
import shutil
import statistics
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from news_ir.data import DocumentStore, read_queries, sha256_file
from news_ir.diagnostics import DEPTHS, ENGINES, diagnose_query, formulation_stability, summarize
from news_ir.evaluation import METRICS, load_qrels, load_run
from news_ir.paired_stats import compare

from evaluate_integrated_study import assert_snapshot, read_trec

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def load_inputs(document_index=None):
    files, scopes, raw_scores = {}, {}, {}

    def bind(path):
        path = Path(path)
        files[path.relative_to(ROOT).as_posix()] = sha256_file(path)
        return path

    def frozen_metrics(folder):
        folder = ROOT / "artifacts/evaluations" / folder
        manifest = json.loads(bind(folder / "manifest.json").read_text(encoding="utf-8"))
        path = bind(folder / "metrics.json")
        if sha256_file(path) != manifest["files"]["metrics.json"]:
            raise ValueError("Frozen metric hash mismatch")
        return json.loads(path.read_text(encoding="utf-8")), manifest

    eligible, corpus_hash = None, None
    if document_index is not None:
        with DocumentStore(document_index) as store:
            eligible = {r[0] for r in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
            corpus_hash = store.manifest["source"]["sha256"]

    for study, query_path, qrel_path, folders, evaluation in [
        ("background", ROOT / "queries.jsonl", ROOT / "qrel.jsonl",
         ("bm25-original-benchmark", "dense-original", "rrf-original-k60"), "rrf-original-57"),
        ("core18", ROOT / "annotations/core18_v1/queries.jsonl", ROOT / "annotations/core18_v1/qrels.jsonl",
         ("bm25-core18-v1", "dense-core18-v1", "rrf-core18-v1"), "integrated-core18-v1"),
    ]:
        queries = read_queries(bind(query_path))
        labels = load_qrels(bind(qrel_path), [q["_id"] for q in queries])
        reference, eval_manifest = frozen_metrics(evaluation)
        if study == "core18":
            protocol_path = ROOT / "annotations/core18_v1/protocol.json"
            protocol = json.loads(bind(protocol_path).read_text(encoding="utf-8"))
            for name, digest in protocol["files"].items():
                if sha256_file(bind(protocol_path.parent / name)) != digest:
                    raise ValueError("Frozen Core 2018 protocol changed")
        runs, scores, source_hashes = {}, {}, set()
        for engine, folder in zip(ENGINES, folders, strict=True):
            directory = ROOT / "artifacts/runs" / folder
            manifest = json.loads(bind(directory / "manifest.json").read_text(encoding="utf-8"))
            expected_manifest = eval_manifest["runs"][engine]["manifest_sha256"]
            if sha256_file(directory / "manifest.json") != expected_manifest:
                raise ValueError("Runs differ from the frozen evaluation")
            source_hashes.add(manifest["corpus_sha256"])
            rows = [json.loads(line) for line in bind(directory / "results.jsonl").read_text(encoding="utf-8").splitlines()]
            candidates = {h["doc_id"] for row in rows for h in row["hits"]}
            runs[engine], _ = load_run(directory, query_path, eligible if eligible is not None else candidates,
                                       expected_source_sha256=corpus_hash or manifest["corpus_sha256"])
            bind(directory / "queries.jsonl")
            bind(directory / "run.trec")
            scores[engine] = {r["query_id"]: {h["doc_id"]: h["score"] for h in r["hits"]} for r in rows}
            expected_engine = {"bm25": "lucene-bm25", "dense": "e5-cosine", "rrf": "rrf"}[engine]
            if manifest["engine"] != expected_engine:
                raise ValueError("Component engine mismatch")
            if engine == "rrf" and manifest["retrieval_config"]["k"] != 60:
                raise ValueError("Expected frozen k=60 RRF")
        if len(source_hashes) != 1:
            raise ValueError("Component corpus identities differ")
        for variant in (["original"] if study == "background" else ["title", "description", "rewrite"]):
            selected = [q for q in queries if study == "background" or q["_id"].endswith("-" + variant)]
            name = study + "/" + variant
            scopes[name] = {"runs": {e: {q["_id"]: runs[e][q["_id"]] for q in selected} for e in ENGINES},
                            "qrels": {q["_id"]: labels[q["_id"]] for q in selected},
                            "queries": {q["_id"]: q["text"] for q in selected},
                            "reference": reference["primary"] if study == "background" else reference["variants"][variant]}
            raw_scores[name] = {q["_id"]: scores["rrf"][q["_id"]] for q in selected}

    # Verify the exact attributed source snapshot, then consume its saved runs.
    provenance = assert_snapshot()
    bind(ROOT / "studies/hamsini_robustness.provenance.json")
    peer = ROOT / "studies/hamsini_robustness"
    labels = {}
    for line in bind(peer / "queries/trec_covid.qrels").read_text(encoding="utf-8").splitlines():
        q, _, d, g = line.split()
        if d in labels.setdefault(q, {}):
            raise ValueError("Duplicate COVID qrel")
        labels[q][d] = int(g)
    reference, _ = frozen_metrics("integrated-covid-v1")
    for variant, suffix in [("original", "query"), ("description", "text"), ("rewrite_a", "rewrite_a"), ("rewrite_b", "rewrite_b")]:
        runs = {}
        for engine in ENGINES:
            path = bind(peer / f"runs/trec_covid/{engine}_{suffix}.run")
            runs[engine] = read_trec(path)
            if engine == "rrf":
                raw = {}
                for line in path.read_text(encoding="utf-8").splitlines():
                    q, _, d, _, score, _ = line.split()
                    raw.setdefault(q, {})[d] = float(score)
                manifest = json.loads(bind(Path(str(path) + ".manifest.json")).read_text(encoding="utf-8"))
                if manifest["config"]["rrf"]["k"] != 60:
                    raise ValueError("Expected imported k=60 RRF")
        query_path = bind(peer / f"queries/trec_covid_{suffix}.tsv")
        texts = dict(line.split("\t", 1) for line in query_path.read_text(encoding="utf-8").splitlines())
        if set(texts) != set(labels):
            raise ValueError("COVID query coverage differs")
        name = "covid/" + variant
        scopes[name] = {"runs": runs, "qrels": labels, "queries": texts, "reference": reference["variants"][variant]}
        raw_scores[name] = raw
    return scopes, raw_scores, files, provenance["commit"] if "commit" in provenance else provenance.get("source_commit"), eligible is not None


def analyze(scopes, raw_scores, *, samples, seed):
    summaries, details, comparisons = {}, {}, {}
    checks = {"reproduced_frozen_per_query_metric_values": 0, "reproduced_frozen_aggregate_metric_values": 0,
              "reconstructed_fusion_scores": 0, "maximum_fusion_score_difference": 0.0}
    for name, scope in scopes.items():
        runs, labels = scope["runs"], scope["qrels"]
        if any(set(r) != set(labels) for r in runs.values()):
            raise ValueError("Scope topic sets differ")
        per_query = {q: diagnose_query({e: runs[e][q] for e in ENGINES}, labels[q]) for q in labels}
        for q, row in per_query.items():
            row["query"] = scope["queries"][q]
            positions = {e: {d: i for i, d in enumerate(runs[e][q], 1)} for e in ("bm25", "dense")}
            for d, published in raw_scores[name][q].items():
                score = sum(1 / (60 + p[d]) for p in positions.values() if d in p)
                delta = abs(score - published)
                if delta > 1e-10:
                    raise ValueError(f"RRF score reconstruction failed: {name}/{q}/{d}: {delta}")
                checks["maximum_fusion_score_difference"] = max(checks["maximum_fusion_score_difference"], delta)
                checks["reconstructed_fusion_scores"] += 1
            for e in ENGINES:
                for m in METRICS:
                    if abs(row["engines"][e][m] - scope["reference"][e]["per_query"][q][m]) > 1e-12:
                        raise ValueError(f"Frozen metric reproduction failed: {name}/{q}/{e}/{m}")
                    checks["reproduced_frozen_per_query_metric_values"] += 1
        summary = summarize(per_query)
        for e in ENGINES:
            for m, value in summary["engines"][e].items():
                if abs(value - scope["reference"][e]["aggregate"][m]) > 1e-12:
                    raise ValueError(f"Aggregate mismatch: {name}/{e}/{m}")
                checks["reproduced_frozen_aggregate_metric_values"] += 1
        scores = {e: {q: r["engines"][e] for q, r in per_query.items()} for e in ENGINES}
        comparisons[name] = {m: [asdict(r) for r in compare(scores, [("rrf", "bm25"), ("rrf", "dense")],
                                                          m, n_resamples=samples, seed=seed)]
                             for m in ("ndcg_at_5", "ap_at_1000")}
        summaries[name], details[name] = summary, per_query
    stability = {}
    for study, control, alternatives in [("core18", "title", ("description", "rewrite")),
                                          ("covid", "original", ("description", "rewrite_a", "rewrite_b"))]:
        stability[study] = {}
        for alt in alternatives:
            stability[study][alt] = {}
            for e in ENGINES:
                def paired(variant):
                    return {q.rsplit("-", 1)[0] if study == "core18" else q: r
                            for q, r in scopes[study + "/" + variant]["runs"][e].items()}
                stability[study][alt][e] = {str(d): formulation_stability(paired(control), paired(alt), depth=d)
                                           for d in (5, 10, 20, 100)}
    return summaries, details, comparisons, stability, checks


def render_report(summaries, details, comparisons, stability, checks):
    lines = ["# Complementarity and fusion diagnostics", "",
        "Human review is deferred. This analysis uses only the existing human benchmark qrels; it creates no relevance labels and does not evaluate the custom 40-query AI-judged pool. Core 2018 rewrite conclusions remain conditional on intent equivalence pending review. COVID rewrite topics 5 and 12 retain the previously documented intent concerns.", "",
        "## What was measured", "",
        "The eight rows below are separate experiments: 57 background-linking queries, three formulations of 50 Core 2018 topics, and four formulations of 50 COVID topics. The 407 formulations are not 407 independent information needs. No aggregate mixes these rows. Rankings, grades, RRF k=60 and all earlier metrics remain unchanged.", "",
        "nDCG@5 uses the existing linear grades; AP@1000 treats any positive grade as relevant. All known positives remain in denominators, including unavailable news records. Unjudged records contribute zero to these metrics but are never described as confirmed nonrelevant. The available news mirror is not an official complete Core 2018 reproduction.", "",
        "## Actual performance and diagnostic ceilings", "",
        "| Study / formulation | n | BM25 | E5 | RRF | Best source per query (oracle) | Ideal ordering of top-20 union (oracle) |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for name, s in summaries.items():
        vals = [s["engines"][e]["ndcg_at_5"] for e in ENGINES]
        lines.append(f"| {name} | {s['query_count']} | " + " | ".join(f"{v:.4f}" for v in vals) +
                     f" | {s['per_query_best_single_oracle_ndcg_at_5']:.4f} | {s['depths']['20']['oracle_union_ndcg_at_5']:.4f} |")
    lines += ["", "Both oracle columns use labels and are explanatory ceilings, not implemented retrieval methods or new achieved results. The best-source oracle chooses a complete engine ranking separately for each topic. The union oracle reorders up to 40 candidates from two top-20 lists using known grades; its larger candidate budget and access to labels prevent a fair claim of deployable improvement. Full top-1,000 union ceilings and recall appear in the JSON/CSV outputs.", "",
        "## Do the engines find different relevant records?", "",
        "Counts below are mean known-positive records per query at depth 20. Unique means absent from the other engine's top 20, not absent from its entire ranking. Jaccard measures ID overlap, not semantic quality.", "",
        "| Study / formulation | Jaccard@20 | BM25-only positives | E5-only positives | Shared positives | Union recall@20 |",
        "|---|---:|---:|---:|---:|---:|"]
    for name, s in summaries.items():
        d = s["depths"]["20"]
        lines.append(f"| {name} | {d['jaccard']:.3f} | {d['bm25_only_known_relevant']:.2f} | {d['dense_only_known_relevant']:.2f} | {d['shared_known_relevant']:.2f} | {d['union_recall']:.3f} |")
    lines += ["", "## Where fusion helps and hurts", "",
        "Each difference is RRF minus its source engine for nDCG@5. Intervals resample paired topics (10,000 draws by default); Holm correction covers the two engine comparisons within each metric and study/formulation row. These are exploratory comparisons, not one family-wide significance claim over all formulations. Win/loss/tie counts use tolerance 1e-12.", "",
        "| Study / formulation | Source | Difference | Paired 95% CI | Holm p | Wins / losses / ties |",
        "|---|---|---:|---|---:|---|"]
    for name, rows in comparisons.items():
        for r in rows["ndcg_at_5"]:
            effect = summaries[name]["fusion_vs_source"][r["run_b"]]
            lines.append(f"| {name} | {r['run_b']} | {r['mean_diff']:+.4f} | [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}] | {r['p_holm']:.4f} | {effect['wins']} / {effect['losses']} / {effect['ties']} |")
    lines += ["", "RRF rewards agreement between lists. A document below both source top fives can enter the fused top five, while a source-only high result can be pushed out. That is a rank mechanism; it does not establish why the embedding model interpreted an article incorrectly. Every query's introduced/removed IDs and known-label counts are saved, including explicit grade-zero versus unjudged distinctions.", "",
        "## Ranking stability under changes to query wording", "",
        "Within-topic top-10 stability is measured without new labels. Jaccard compares membership; mean prefix overlap also responds to order, averaging intersection size divided by the larger prefix length at ranks 1 through 10 (or the longer list's actual length if shorter). Identical empty lists have agreement 1. Stability is not evidence that a rewrite preserved meaning, and official descriptions also change length and detail.", "",
        "| Study / alternative | Engine | Jaccard@10 | Mean prefix overlap@10 |",
        "|---|---|---:|---:|"]
    for study, alternatives in stability.items():
        for alt, engines in alternatives.items():
            for e, values in engines.items():
                a = values["10"]["aggregate"]
                lines.append(f"| {study}/{alt} | {e} | {a['jaccard']:.3f} | {a['mean_prefix_overlap']:.3f} |")
    lines += ["", "## Cases to inspect in the demo", "",
        "These cases are selected after seeing results: the largest improvement and largest deterioration against the better single engine, within Core title and provisional rewrite queries. They illustrate mechanisms and are not an unbiased sample.", ""]
    for name in ("core18/title", "core18/rewrite"):
        candidates = details[name]
        key = lambda q: candidates[q]["engines"]["rrf"]["ndcg_at_5"] - candidates[q]["per_query_best_single_ndcg_at_5"]
        chosen = list(dict.fromkeys([max(candidates, key=key), min(candidates, key=key)]))
        for q in chosen:
            row = candidates[q]
            lines += [f"### {name} · {q}", "", row["query"], "",
                      f"RRF minus the better single engine: {key(q):+.4f} nDCG@5.", "",
                      "| Fused rank | Article ID | BM25 rank | E5 rank | Known grade/status |",
                      "|---:|---|---:|---:|---|"]
            for h in row["fusion_top5"]:
                ranks = h["fusion"]["component_ranks"]
                grade = str(h["known_grade"]) if h["known_grade"] is not None else "unjudged"
                lines.append(f"| {h['rank']} | `{h['doc_id']}` | {ranks['bm25'] or 'outside list'} | {ranks['dense'] or 'outside list'} | {grade} |")
            lines.append("")
    lines += ["## Reproduction and limits", "",
        "Run `python scripts/analyze_complementarity.py --output artifacts/evaluations/complementarity-v2` for a new version; existing output directories are refused. Add `--document-index artifacts/indexes/bm25` to also recheck news result membership in the local eligible corpus. The default works from saved rankings without raw articles, models or indexes; it verifies input hashes, frozen query/run alignment and historical corpus identity, but does not revalidate corpus-wide coverage.", "",
        f"Checks reproduced {checks['reproduced_frozen_per_query_metric_values']:,} frozen per-query metric values and {checks['reproduced_frozen_aggregate_metric_values']:,} aggregate values. All {checks['reconstructed_fusion_scores']:,} published RRF scores reconstruct from full component ranks (maximum absolute difference {checks['maximum_fusion_score_difference']:.3g}; tolerance 1e-10 for serialized imported scores). These are regression/consistency checks, not another independent evaluator.", "",
        "The imported COVID runs and source attribution remain unchanged. Their published score/doc-ID tie convention is preserved; no runs are reranked to improve results. No hyperparameter was selected from this analysis, no custom human labels were created, and no assessor agreement is claimed. The existing offline review pack is preserved for a later round.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evaluations/complementarity-v1")
    parser.add_argument("--document-index", type=Path)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20261102)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    target = args.output.resolve()
    if target.exists():
        raise FileExistsError("Diagnostic output exists; choose a new version")
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        scopes, raw_scores, inputs, commit, corpus_checked = load_inputs(args.document_index)
        summaries, details, paired, stability, checks = analyze(scopes, raw_scores, samples=args.samples, seed=args.seed)
        write(working / "summary.json", summaries)
        write(working / "per_query.json", details)
        write(working / "paired_comparisons.json", paired)
        write(working / "formulation_stability.json", stability)
        write(working / "checks.json", checks)
        with (working / "per_query_depth.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = None
            for name, rows in details.items():
                for q, row in rows.items():
                    for depth, values in row["depths"].items():
                        flat = {"scope": name, "query_id": q, "query": row["query"], "depth": depth,
                                **{m: v for m, v in values.items() if m != "label_counts"},
                                **{f"{e}_{m}": v for e, counts in values["label_counts"].items() for m, v in counts.items()}}
                        if writer is None:
                            writer = csv.DictWriter(stream, fieldnames=list(flat))
                            writer.writeheader()
                        writer.writerow(flat)
        (working / "REPORT.md").write_text(render_report(summaries, details, paired, stability, checks), encoding="utf-8", newline="\n")
        for name, digest in inputs.items():
            if sha256_file(ROOT / name) != digest:
                raise ValueError("An input changed during analysis: " + name)
        manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "diagnostic": "complementarity-v1",
                    "scopes": {n: s["query_count"] for n, s in summaries.items()},
                    "policy": "Separate studies and formulations; existing human qrels only; fixed k=60; no new retrieval or labels",
                    "depths": list(DEPTHS), "samples": args.samples, "seed": args.seed,
                    "paired_correction": "Holm across two source comparisons within each metric/scope; exploratory",
                    "news_eligible_membership_rechecked": corpus_checked,
                    "human_review": "deferred; existing review pack preserved; no human responses created",
                    "imported_source_commit": commit, "inputs": inputs,
                    "code": {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in
                             (Path(__file__), ROOT / "src/news_ir/diagnostics.py", ROOT / "src/news_ir/fusion.py",
                              ROOT / "src/news_ir/evaluation.py", ROOT / "src/news_ir/paired_stats.py",
                              ROOT / "scripts/evaluate_integrated_study.py")},
                    "files": {p.name: sha256_file(p) for p in working.iterdir() if p.is_file()}}
        write(working / "manifest.json", manifest)
        working.rename(target)
        print(json.dumps({"output": str(target), "scopes": manifest["scopes"], "checks": checks}, indent=2))
    except BaseException:
        shutil.rmtree(working)
        raise


if __name__ == "__main__":
    main()

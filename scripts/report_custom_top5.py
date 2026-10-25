"""Report all 20 top-five assessments, content quality and input visibility.

Reads existing decisions; never assigns or changes a relevance grade.
"""

import json
import os
from collections import Counter
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("artifacts/plot-cache").resolve()))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from news_ir.assessment import validate_assessments
from news_ir.data import sha256_file
from report_current_study import visibility_audit


ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "artifacts/assessments/custom20-v1"
ANNOTATION = ROOT / "annotations/ai_study_v1"
EVALUATION = ROOT / "artifacts/evaluations/custom20-top5-v1"
FIGURES = ROOT / "reports/figures/custom20-top5"
NAMES = {"bm25": "BM25", "dense": "E5 dense"}
CATEGORIES = {"vocabulary_mismatch": "Vocabulary mismatch", "negation": "Negation",
              "homonym": "Word sense", "temporal": "Temporal"}
COLORS = {"bm25": "#3477a8", "dense": "#d97a29"}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def save(fig, name):
    for extension in ("png", "svg", "pdf"):
        fig.savefig(FIGURES / f"{name}.{extension}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    labels_path = ANNOTATION / "assessments.top5.jsonl"
    validation = validate_assessments(POOL, labels_path)
    manifest = json.loads((EVALUATION / "manifest.json").read_text())
    if manifest["assessments_sha256"] != sha256_file(labels_path):
        raise ValueError("Assessments differ from the evaluated snapshot")
    for name, digest in manifest["files"].items():
        if sha256_file(EVALUATION / name) != digest:
            raise ValueError(f"Evaluation file hash mismatch: {name}")
    metrics = json.loads((EVALUATION / "metrics.json").read_text())
    paired = json.loads((EVALUATION / "paired_comparison.json").read_text())
    uncertainty = json.loads((EVALUATION / "grade_uncertainty.json").read_text())
    labels = list(map(json.loads, labels_path.read_text().splitlines()))
    lookup = {(r["query_id"], r["doc_id"]): r for r in labels}
    articles = {(r["query_id"], r["doc_id"]): r for r in map(json.loads, (POOL / "articles.blinded.jsonl").read_text().splitlines())}
    provenance = {(r["query_id"], r["doc_id"]): r for r in map(json.loads, (POOL / "pool.provenance.jsonl").read_text().splitlines())}
    queries = list(map(json.loads, (ANNOTATION / "queries.jsonl").read_text().splitlines()))
    visibility = visibility_audit(labels, scope="top-five study")
    dump(ANNOTATION / "evidence_visibility.top5.json", visibility)
    quality = {}
    for engine in NAMES:
        selected = [(pair, articles[pair]) for pair in lookup if 0 < provenance[pair]["component_ranks"].get(engine, 1001) <= 5]
        duplicate_slots = 0
        for query in queries:
            hashes = [a["contents_sha256"] for pair, a in selected if pair[0] == query["_id"]]
            duplicate_slots += len(hashes) - len(set(hashes))
        quality[engine] = {"top5_slots": len(selected), "empty_body_slots": sum(not a["text"].strip() for _, a in selected),
                           "body_under_200_characters_slots": sum(len(a["text"].strip()) < 200 for _, a in selected),
                           "duplicate_content_slots_within_query": duplicate_slots}
    dump(ANNOTATION / "content_quality.top5.json", {"scope": "Descriptive counts; no filtering or reranking",
         "near_empty_definition": "Body shorter than 200 Unicode characters, including empty bodies",
         "duplicate_definition": "Additional identical title+body hashes within an engine/query top five",
         "engines": quality, "assessed_pairs": len(labels), "unique_document_ids": len({r["doc_id"] for r in labels}),
         "unique_contents_hashes": len({r["contents_sha256"] for r in labels})})

    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(8.8, 3.7), constrained_layout=True)
    for offset, engine in enumerate(NAMES):
        values = [metrics["by_category"][c][engine]["ndcg_at_5"] for c in CATEGORIES]
        bars = ax.bar([i + (offset - .5) * .36 for i in range(4)], values, width=.36,
                      label=NAMES[engine], color=COLORS[engine])
        ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax.set_xticks(range(4), list(CATEGORIES.values()))
    ax.set(ylim=(0, 1), ylabel="nDCG@5: linear gains", title="Custom 20: five AI-assessed queries per category")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "category_ndcg")
    fig, ax = plt.subplots(figsize=(11, 3.5), constrained_layout=True)
    values = [metrics["per_query"][q["_id"]]["dense"]["ndcg_at_5"] - metrics["per_query"][q["_id"]]["bm25"]["ndcg_at_5"] for q in queries]
    ax.bar([q["_id"] for q in queries], values, color=[COLORS["dense"] if v > 0 else COLORS["bm25"] for v in values])
    ax.axhline(0, color="black", linewidth=.7)
    ax.set(ylabel="E5 minus BM25 nDCG@5", title="Custom top-five study: per-query differences (AI labels)")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "per_query_difference")

    grades, confidence = Counter(r["grade"] for r in labels), Counter(r["confidence"] for r in labels)
    lines = ["# Custom 20-query study: complete top-five assessment", "",
             "Completed on 25 October 2026: all **188 query–article pairs** in the union of both engines' top five "
             "have full-available-article AI assessments. All 20 fixed queries are represented; 100% of both engines' top-five slots "
             "are assessed. The larger depth-20 pool has **549 unassessed pairs**. This is a complete top-five analysis, "
             "not a complete pooled MAP study. Human review is planned next; see [assessment method](ASSESSMENT_METHOD.md).", "",
             "## Primary results", "", "| Measure | BM25 | E5 dense |", "| --- | ---: | ---: |"]
    for measure, name in (("ndcg_at_5", "nDCG@5 (linear 0–2 gains)"), ("precision_at_5", "Precision@5"), ("judged_at_5", "Assessed fraction at 5")):
        lines.append(f"| {name} | {metrics['macro_over_completed_queries_only']['bm25'][measure]:.6f} | {metrics['macro_over_completed_queries_only']['dense'][measure]:.6f} |")
    lines += ["", "**MAP@1000 is withheld** until the designated depth-20 pool is assessed. "
              "Its eventual value will still be a shallow-pool estimate, not exhaustive corpus recall. "
              "nDCG's ideal ranking is based only on known assessed positives and may change when deeper positives are found.", "",
              "Queries **V01, V05 and T01** have no positives in the assessed top-five union. They remain in the macro average "
              "with nDCG/P=0 under the declared zero-positive convention. This does not establish absence of relevant articles "
              "in the corpus or deeper pool; it flags the limits of this shallow study.", "",
              "| Category (five queries each) | BM25 nDCG@5 | E5 nDCG@5 | E5 wins / BM25 wins / ties |", "| --- | ---: | ---: | --- |"]
    for category in CATEGORIES:
        group = metrics["by_category"][category]
        delta = [metrics["per_query"][q]["dense"]["ndcg_at_5"] - metrics["per_query"][q]["bm25"]["ndcg_at_5"] for q in group["query_ids"]]
        lines.append(f"| {CATEGORIES[category]} | {group['bm25']['ndcg_at_5']:.6f} | {group['dense']['ndcg_at_5']:.6f} | "
                     f"{sum(d>1e-12 for d in delta)} / {sum(d < -1e-12 for d in delta)} / {sum(abs(d)<=1e-12 for d in delta)} |")
    lines += ["", "![Category comparison](figures/custom20-top5/category_ndcg.png)", "",
              "## What the negation results mean", "",
              "Across all five negation queries, **E5 wins three and BM25 wins two**. E5's category mean is "
              "**0.664864**, compared with **0.643358** for BM25. The earlier Ebola example (N03) is one of E5's losses, "
              "not representative evidence that BM25 generally handles negation better.", "",
              "E5 is a bi-encoder: it encodes queries and articles separately for similarity matching. "
              "A high similarity score need not enforce a logical constraint. BM25 is also not a Boolean negation reasoner; "
              "its performance can benefit from exact entities, evidence wording and full-body coverage. "
              "[NevIR (Weller, Lawrie and Van Durme, EACL 2024)](https://aclanthology.org/2024.eacl-long.139/) "
              "reports substantial negation difficulty across neural retrieval architectures, including weak bi-encoder performance. "
              "That motivates a controlled test; it does not dictate which engine must win our news queries.", "",
              "Full text also changes apparent polarity. N01's article with a negative headline contains Reich's empirical "
              "Seattle study finding no employment reduction, so it is relevant under the frozen mixed-article rule. "
              "Likewise, some marriage-ban stories report both restrictive and permissive decisions. "
              "We judge whether the requested evidence is present, rather than treating every contrary headline as grade 0.", "",
              "## Per-query results", "", "| ID | Category | Known pool positives | BM25 nDCG@5 | E5 nDCG@5 |", "| --- | --- | ---: | ---: | ---: |"]
    for query in queries:
        qid = query["_id"]
        row = metrics["per_query"][qid]
        positives = sum(r["grade"] > 0 for r in labels if r["query_id"] == qid)
        lines.append(f"| {qid} | {CATEGORIES[query['category']]} | {positives} | {row['bm25']['ndcg_at_5']:.6f} | {row['dense']['ndcg_at_5']:.6f} |")
    lo, hi = paired["paired_bootstrap_95_percentile_ci"]
    bounds = uncertainty["macro_difference_bounds"]
    lines += ["", "![Per-query differences](figures/custom20-top5/per_query_difference.png)", "",
              "## Uncertainty and validation", "",
              f"E5 wins **{paired['dense_wins']}** queries, BM25 wins **{paired['bm25_wins']}**, and **{paired['ties']}** tie. "
              f"Mean E5-minus-BM25 nDCG is **{paired['mean_difference']:+.6f}**; the descriptive paired 95% bootstrap interval "
              f"is **[{lo:+.6f}, {hi:+.6f}]**, including zero (10,000 draws, seed 20261025). "
              "The suite is small, some needs overlap, and this is a preliminary reference, with human review planned next ([review plan](ASSESSMENT_METHOD.md)). No general winner is established.", "",
              f"The label distribution is **0: {grades[0]}, 1: {grades[1]}, 2: {grades[2]}**; confidence is "
              f"**high: {confidence['high']}, medium: {confidence['medium']}**. Confidence is the assessor's own rating, not calibration. "
              "For an additional robustness check, every medium-confidence label was allowed to take every possible grade 0/1/2 "
              "within its query, while high-confidence labels stayed fixed. These extreme scenarios give an overall difference range "
              f"of **[{bounds[0]:+.6f}, {bounds[1]:+.6f}]**. This is not a statistical interval or a replacement judgment set; "
              "the stored decisions were not changed. `grade_uncertainty.json` provides per-query bounds.", "",
              f"All **{manifest['independent_metric_comparisons']}** independent native `trec_eval` nDCG@5/P@5 comparisons passed "
              "for both engines under linear and exp2 gains. Exact quotation offsets, content hashes, pair uniqueness and pool membership "
              "validate for all 188 decisions. Original data, original 57-query qrels/runs and the earlier 16-pair pilot are preserved.", "",
              "## Content quality and coverage", "", "| Top-five slots across 20 queries | BM25 | E5 dense |", "| --- | ---: | ---: |"]
    for key, name in (("top5_slots", "Total ranked slots"), ("empty_body_slots", "Empty-body slots"),
                      ("body_under_200_characters_slots", "Body shorter than 200 characters, including empty"),
                      ("duplicate_content_slots_within_query", "Additional identical-content slots within query")):
        lines.append(f"| {name} | {quality['bm25'][key]} | {quality['dense'][key]} |")
    lines += ["", "These are descriptive diagnostics. Both baselines continue to search the same eligible corpus; "
              "title-only documents were retained in the original preprocessing. No result was silently filtered or deduplicated. "
              "Exact-content duplication occurs in both engines and is separate from semantic reasoning.", "",
              f"The exact pinned-tokenizer audit finds **{visibility['truncated_pairs']} of 188** assessed records truncated by E5's "
              f"512-token passage budget, with **{visibility['empty_body_pairs']}** empty-body pairs. "
              "`evidence_visibility.top5.json` records visibility of each quoted evidence span. BM25 indexes full bodies; "
              "visibility is an input-coverage measure, not attention or a causal explanation of scoring.", "",
              "A fresh offline CPU search of the full dense index reproduced **the exact same five IDs in the same order** "
              "for H02: five identical `Results` titles with empty bodies. The maximum absolute score difference from the "
              "saved Kaggle run was 1.79e-7. This reproduces the surprising pattern independently of the cloud export; "
              "it does not by itself establish the internal cause. The local search took about 37.2 seconds including query "
              "encoding and FAISS IPC/search, excluding startup and article lookup; it is not a controlled latency benchmark. "
              "Raw output is saved at `artifacts/analysis/custom20-top5/local_h02_search.json`.", "",
              "Temporal judgments use the inclusive windows in the frozen suite. Relative event dates are accepted when anchored "
              "by explicit narrative timing and the named event in the query; the rationale states the derivation. "
              "Several grade-0 records are topically relevant but lack enough text to verify the window. "
              "Such grades express failure of the evidence requirement, not proof that the actual historical event was outside the window. "
              "No dates were inferred from UUIDs or an assumed publication date. Review medium-confidence date bounds before treating temporal scores as definitive.", "",
              "## Reproduce and continue", "", "```sh", ".venv/bin/python scripts/evaluate_custom_top5.py --output artifacts/evaluations/custom20-top5-rechecked",
              ".venv/bin/python scripts/report_custom_top5.py", ".venv/bin/python -m pytest -q", "```", "",
              "The report reads the canonical evaluation; evaluator outputs are versioned and refuse overwrites. "
              "The assessment appendix links every decision to exact stored evidence. The next required stage is the remaining "
              "549 depth-20 candidates, followed by pooled MAP and the comparison demo. A later controlled negation minimal-pair "
              "test and a symmetric content-quality/deduplication ablation can help isolate causes; neither has been applied to these scores.", ""]
    (ROOT / "reports/CUSTOM_20_TOP5.md").write_text("\n".join(lines))

    appendix = ["# Custom top-five assessment evidence appendix", "",
                "188 full-article AI decisions for preliminary comparison; human review is planned next ([review plan](ASSESSMENT_METHOD.md)); exact duplicates were read once and retained by ID. "
                "Ranks below are revealed for analysis after grading. Exact source character spans and hashes are in "
                "`annotations/ai_study_v1/assessments.top5.jsonl`. Empty bodies are not recovered from external sources.", ""]
    for query in queries:
        qid = query["_id"]
        appendix += [f"## {qid}: {query['text']}", "", f"Include: {query['relevant_if']}", "", f"Exclude: {query['exclude_if']}", ""]
        for pair, decision in lookup.items():
            if pair[0] != qid:
                continue
            article, ranks = articles[pair], provenance[pair]["component_ranks"]
            appendix += [f"### {article['title']}", "", f"ID: `{pair[1]}`. Grade **{decision['grade']}**, "
                         f"confidence **{decision['confidence']}**. BM25 rank: {ranks.get('bm25', 'outside pool')}; "
                         f"E5 rank: {ranks.get('dense', 'outside pool')}.", "", decision["rationale"], ""]
            for span in decision["evidence"]:
                appendix += ["> " + span["quote"].replace("\n", " "), ""]
    (ROOT / "reports/CUSTOM_20_ASSESSMENT_EVIDENCE.md").write_text("\n".join(appendix))
    print(json.dumps({"report": "reports/CUSTOM_20_TOP5.md", "appendix": "reports/CUSTOM_20_ASSESSMENT_EVIDENCE.md",
                      "validated_pairs": validation["assessed_pairs"], "content_quality": quality,
                      "truncated_pairs": visibility["truncated_pairs"], "figures": str(FIGURES)}, indent=2))


if __name__ == "__main__":
    main()

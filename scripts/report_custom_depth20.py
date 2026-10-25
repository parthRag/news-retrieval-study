"""Generate the complete pooled-study report, evidence appendix and figures."""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("artifacts/plot-cache").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from news_ir.assessment import validate_assessments
from news_ir.custom_depth20 import dump
from news_ir.data import sha256_file
from report_current_study import visibility_audit


ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "artifacts/assessments/custom20-v1"
ANN = ROOT / "annotations/ai_study_v1"
EVAL = ROOT / "artifacts/evaluations/custom20-depth20-v1"
FIG = ROOT / "reports/figures/custom20-depth20"
NAMES = {"bm25": "BM25", "dense": "E5 dense"}
COLORS = {"bm25": "#3477a8", "dense": "#d97a29"}
CATEGORIES = {"vocabulary_mismatch": "Vocabulary mismatch", "negation": "Negation", "homonym": "Word sense", "temporal": "Temporal"}


def main():
    labels_path = ANN / "assessments.depth20.jsonl"
    validation = validate_assessments(POOL, labels_path)
    manifest = json.loads((EVAL / "manifest.json").read_text())
    if not validation["complete_pool"] or manifest["assessments_sha256"] != sha256_file(labels_path):
        raise ValueError("Complete labels must match the evaluated assessment snapshot")
    for f, digest in manifest["files"].items():
        if sha256_file(EVAL / f) != digest:
            raise ValueError(f"Evaluation artifact changed: {f}")
    metrics = json.loads((EVAL / "metrics.json").read_text())
    groups = json.loads((EVAL / "by_category.json").read_text())
    paired = json.loads((EVAL / "paired_comparison.json").read_text())
    sensitivity = json.loads((EVAL / "sensitivity.json").read_text())
    labels = list(map(json.loads, labels_path.read_text().splitlines()))
    articles = {(r["query_id"], r["doc_id"]): r for r in map(json.loads, (POOL / "articles.blinded.jsonl").read_text().splitlines())}
    provenance = {(r["query_id"], r["doc_id"]): r for r in map(json.loads, (POOL / "pool.provenance.jsonl").read_text().splitlines())}
    queries = list(map(json.loads, (ANN / "queries.jsonl").read_text().splitlines()))
    primary = metrics["linear"]
    visibility = visibility_audit(labels, scope="complete depth-20 pool")
    dump(ANN / "evidence_visibility.depth20.json", visibility)
    quality = {}
    for engine in NAMES:
        selected = [(pair, a) for pair, a in articles.items() if engine in provenance[pair]["component_ranks"]]
        duplicate_slots = 0
        for query in queries:
            hashes = [a["contents_sha256"] for pair, a in selected if pair[0] == query["_id"]]
            duplicate_slots += len(hashes) - len(set(hashes))
        quality[engine] = {"top20_slots": len(selected), "empty_body_slots": sum(not a["text"].strip() for _, a in selected),
                           "body_under_200_characters_slots": sum(len(a["text"].strip()) < 200 for _, a in selected),
                           "duplicate_content_slots_within_query": duplicate_slots}
    exact = defaultdict(set)
    for r in labels:
        exact[r["query_id"], r["contents_sha256"]].add(r["grade"])
    if any(len(v) > 1 for v in exact.values()):
        raise ValueError("Identical content under the same query has conflicting grades")
    dump(ANN / "content_quality.depth20.json", {"scope": "Descriptive top-20 counts; no filtering or reranking",
         "engines": quality, "assessed_pairs": len(labels), "unique_document_ids": len({r["doc_id"] for r in labels}),
         "unique_contents_hashes": len({r["contents_sha256"] for r in labels}),
         "same_query_exact_content_grade_conflicts": 0, "explicit_hash_reuses": sum("judgment_reuse" in r for r in labels)})
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), constrained_layout=True)
    for ax, metric, title in zip(axes, ("ndcg_at_5", "ap_at_1000"), ("nDCG@5 (linear gains)", "Pooled MAP@1000")):
        for j, e in enumerate(NAMES):
            bars = ax.bar([i + (j-.5)*.36 for i in range(4)], [groups[c][e][metric] for c in CATEGORIES],
                          width=.36, label=NAMES[e], color=COLORS[e])
            ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
        ax.set_xticks(range(4), ["Vocabulary", "Negation", "Word sense", "Temporal"])
        ax.set(ylim=(0, 1.03), ylabel="Macro mean: five queries per category", title=title)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(FIG / f"category_metrics.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(11, 5.4), constrained_layout=True)
    for ax, metric, label in zip(axes, ("ndcg_at_5", "ap_at_1000"), ("nDCG@5", "AP@1000")):
        delta = [primary["dense"]["per_query"][q["_id"]][metric] - primary["bm25"]["per_query"][q["_id"]][metric] for q in queries]
        ax.bar([q["_id"] for q in queries], delta, color=[COLORS["dense"] if d > 0 else COLORS["bm25"] for d in delta])
        ax.axhline(0, color="black", linewidth=.6)
        ax.set(ylabel=f"E5 minus BM25 {label}", ylim=(-1.05, 1.05))
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Custom 20: preliminary comparison, complete top-20 union")
    for ext in ("png", "svg", "pdf"):
        fig.savefig(FIG / f"per_query_differences.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)
    lines = ["# Custom 20: complete pooled assessment", "",
             "All **737 query–article pairs** in the union of BM25 and E5's top 20 are assessed. "
             "This adds **549** decisions to the preserved 188-pair top-five snapshot. Every record has a 0–2 grade, "
             "rationale, confidence, exact Unicode evidence offsets, full-available-text reading acknowledgment and source hash. "
             "This preliminary comparison uses full-article AI judgments; human review is planned next. See [assessment method and review plan](ASSESSMENT_METHOD.md). The frozen queries, retrieval runs and original 57-query qrels are unchanged.", "",
             "## Quantitative results", "", "Macro means include all 20 queries, including V05 with no known relevant pool article. "
             "Saved runs contain up to 1,000 results per query; judgments cover every top-20 result, not all 1,000.", "",
             "| Measure | BM25 | E5 dense |", "| --- | ---: | ---: |"]
    for m, name in (("ndcg_at_5", "nDCG@5, linear 0–2"), ("ndcg_at_10", "nDCG@10"),
                    ("ap_at_1000", "Pooled MAP@1000"), ("precision_at_5", "Precision@5"),
                    ("precision_at_10", "Precision@10"), ("recall_at_1000", "Recall@1000 of known pool positives"),
                    ("judged_at_20", "Judged fraction at 20"), ("judged_at_1000", "Judged fraction at 1,000")):
        lines.append(f"| {name} | {primary['bm25']['aggregate'][m]:.6f} | {primary['dense']['aggregate'][m]:.6f} |")
    lines += ["", "**Interpretation:** AP divides by all known positive judgments in the complete designated pool. "
              "Unjudged hits retain their original rank and contribute zero to the calculation; they are not confirmed irrelevant. "
              "The depth-20 pool is shallow relative to 594,589 eligible articles, so these MAP/recall estimates cannot establish exhaustive corpus effectiveness. "
              "V05's zero score means no qualifying match was found in this pool, not that the corpus has no answer.", "",
              "## What changed from the top-five snapshot", "",
              "The earlier [188-pair result](CUSTOM_20_TOP5.md) remains a historical snapshot. "
              "Its nDCG@5 was 0.514902 / 0.528590. Deeper judgments discover more highly relevant articles and enlarge "
              "the ideal-ranking denominator, so current nDCG falls even though every original top-five grade and ranking is unchanged. "
              "Precision@5 remains 0.53 for both. V01 and T01 now have known deeper positives; V05 remains the only zero-positive pool query.", "",
              "| Category | BM25 nDCG@5 | E5 nDCG@5 | BM25 pooled MAP | E5 pooled MAP |", "| --- | ---: | ---: | ---: | ---: |"]
    for c, name in CATEGORIES.items():
        lines.append(f"| {name} | {groups[c]['bm25']['ndcg_at_5']:.6f} | {groups[c]['dense']['ndcg_at_5']:.6f} | {groups[c]['bm25']['ap_at_1000']:.6f} | {groups[c]['dense']['ap_at_1000']:.6f} |")
    lines += ["", "![Category results](figures/custom20-depth20/category_metrics.png)", "", "## Paired uncertainty", "",
              "10,000 paired query-bootstrap draws, seed 20261025. These intervals describe variability over this small suite, "
              "not AI-label accuracy. Related needs and shared articles limit independence. Both intervals include zero; do not claim a general winner.", "",
              "| E5 minus BM25 | Mean | Descriptive 95% percentile interval | E5 / BM25 wins / ties |", "| --- | ---: | --- | --- |"]
    for m, r in paired["metrics"].items():
        lo, hi = r["paired_bootstrap_95_percentile_ci"]
        lines.append(f"| {m} | {r['mean_dense_minus_bm25']:+.6f} | [{lo:+.6f}, {hi:+.6f}] | {r['dense_wins']} / {r['bm25_wins']} / {r['ties']} |")
    lines += ["", "## Reading and grading safeguards", "",
              "Full stored titles and bodies were read, including long policy digests in explicit consecutive chunks. "
              "Only an exact repeated extraction glossary was removed from the reading display. Exact title+body duplicates can reuse a decision "
              "only under the same query; 13 such copies carry explicit source-ID provenance, and all identical same-query contents have consistent grades. "
              "Blinded packets hide engine/rank/score, but prior results were seen, so perfect assessor blindness is not claimed.", "",
              "The distribution is **398 grade 0, 110 grade 1 and 229 grade 2**; **625 high- and 112 medium-confidence** assessments. "
              "Confidence is self-rating, not calibrated reliability. Grade 0 can mean failure to supply mandatory evidence: for temporal queries, "
              "a topically relevant report with no bounded event date does not satisfy the requested window. It does not prove that its real-world event was outside it. "
              "Saved decisions state the assessor's chosen interpretation and flag borderline cases; confidence does not replace independent review.", "",
              "Temporal judgments use explicit dates or explained relative bounds from the article and named query anchor. "
              "UUIDs, publication metadata and linked-video dates were not substituted for event dates. Some text contains dating errors: "
              "T01's short snap-election retrospective says May became prime minister 'last June'; its medium-confidence grade follows the stored text and is a source-quality concern.", "",
              "## Sensitivity checks", "", "| Scenario | BM25 nDCG@5 | E5 nDCG@5 | BM25 pooled MAP | E5 pooled MAP |", "| --- | ---: | ---: | ---: | ---: |"]
    exp = metrics["exp2"]
    lines.append(f"| Exponential gains 0,1,3 | {exp['bm25']['aggregate']['ndcg_at_5']:.6f} | {exp['dense']['aggregate']['ndcg_at_5']:.6f} | {exp['bm25']['aggregate']['ap_at_1000']:.6f} | {exp['dense']['aggregate']['ap_at_1000']:.6f} |")
    for scenario, values in sensitivity["scenarios"].items():
        lines.append(f"| {scenario} | {values['bm25']['ndcg_at_5']:.6f} | {values['dense']['ndcg_at_5']:.6f} | {values['bm25']['ap_at_1000']:.6f} | {values['dense']['ap_at_1000']:.6f} |")
    lines += ["", "`medium_as_zero` removes positive credit for every medium-confidence decision; `grade2_only` removes grade-1 credit. "
              "These are specified robustness scenarios, not exhaustive uncertainty bounds, corrected labels or confidence intervals. Original judgments remain unchanged.", "",
              "## Failure-analysis implications", "",
              "- **Vocabulary mismatch:** the workforce query has deeper technology-layoff matches; both top-five lists initially missed the required sector. "
              "Better synonym matching alone does not ensure all constraints hold.",
              "- **Negation:** the fixed five-query category still has three E5 wins and two BM25 wins at nDCG@5. "
              "Both systems can retrieve topical contradictions. Mixed articles may qualify when they explicitly include the requested evidence. "
              "[NevIR](https://aclanthology.org/2024.eacl-long.139/) motivates testing neural negation rather than assuming similarity enforces it.",
              "- **Word sense and document quality:** H02's dense top-five empty `Results` records remain a concrete failure. "
              "Deeper results contain real India match reports, plus wrong teams, domestic cricket and previews. "
              "H04 contains many conservation articles about cheetahs, wolves or pandas; correct broad topic is insufficient for jaguar-specific relevance.",
              "- **Temporal evidence:** T01 has dated first-week and fifteen-day Brexit retrospectives below rank five. "
              "A later publication can answer an earlier event window, whereas an undated relevant-looking account may not. "
              "T03 distinguishes actual state rulings, stayed rulings and the excluded nationwide decision.",
              "- **Coverage confound:** BM25 indexes full bodies; E5 encodes a passage-prefixed 512-token input. "
              "Visibility counts describe what text was retained, not model attention or proof that truncation caused a particular score.", "",
              "## Content quality and input visibility", "", "| Top-20 diagnostic | BM25 | E5 dense |", "| --- | ---: | ---: |"]
    for key in ("top20_slots", "empty_body_slots", "body_under_200_characters_slots", "duplicate_content_slots_within_query"):
        lines.append(f"| {key} | {quality['bm25'][key]} | {quality['dense'][key]} |")
    lines += ["", f"The pinned tokenizer truncates **{visibility['truncated_pairs']}/737** assessed pairs. "
              "Every quoted span's input visibility is stored in `annotations/ai_study_v1/evidence_visibility.depth20.json`. "
              "No baseline filtering, deduplication, query rewriting or parameter tuning was applied. "
              "A symmetric quality ablation and controlled negation minimal pairs are useful next experiments; they are not completed here.", "",
              "## Per-query results", "", "| Query | Known positives | BM25 nDCG@5 | E5 nDCG@5 | BM25 AP@1000 | E5 AP@1000 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for q in queries:
        qid = q["_id"]
        b, d = primary["bm25"]["per_query"][qid], primary["dense"]["per_query"][qid]
        lines.append(f"| {qid} | {b['known_relevant']} | {b['ndcg_at_5']:.6f} | {d['ndcg_at_5']:.6f} | {b['ap_at_1000']:.6f} | {d['ap_at_1000']:.6f} |")
    lines += ["", "![Per-query differences](figures/custom20-depth20/per_query_differences.png)", "", "## Reproduction", "",
              "All **588** native `trec_eval` comparisons passed: both engines × linear/exp2 × 20 queries plus macro × seven measures. "
              "Input hashes, pool membership/component ranks, all evidence spans and preservation of the earlier 188 records are checked before publication. "
              "Evaluation writes atomically to a fresh directory and requires complete designated-pool coverage.", "", "```sh",
              ".venv/bin/python scripts/evaluate_custom_depth20.py --output artifacts/evaluations/custom20-depth20-recheck",
              ".venv/bin/python scripts/report_custom_depth20.py", ".venv/bin/python -m pytest -q", "```", "",
              "See [all 737 decisions](CUSTOM_20_DEPTH20_EVIDENCE.md), `artifacts/evaluations/custom20-depth20-v1/per_query.csv`, "
              "the versioned JSONL labels, and generated PNG/SVG/PDF figures. The original 57-query benchmark and RRF experiment remain separate. "
              "Group details, contribution ownership and GitHub URL remain placeholders; PDF creation remains deferred."]
    (ROOT / "reports/CUSTOM_20_DEPTH20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    appendix = ["# Complete custom-pool AI assessment evidence", "", "737 fixed query–article decisions, grades 0–2. "
                "Full-article AI judgments support this preliminary reference; human review is planned next. See [assessment method](ASSESSMENT_METHOD.md). Evidence offsets are Unicode characters into `(title + newline + body).strip()`. "
                "Titles/quotes below support the saved rationale; full-available-text reading was used. Original 188 records are preserved.", ""]
    for q in queries:
        qid = q["_id"]
        appendix += [f"## {qid}: {q['text']}", "", f"Include: {q['relevant_if']}", "", f"Exclude: {q['exclude_if']}", ""]
        for row in sorted((r for r in labels if r["query_id"] == qid), key=lambda r: r["doc_id"]):
            article = articles[qid, row["doc_id"]]
            appendix += [f"### `{row['doc_id']}` — {article['title']}", "", f"Grade **{row['grade']}**; confidence **{row['confidence']}**.", "", row["rationale"], ""]
            for ev in row["evidence"]:
                appendix += [f"> {ev['quote']}", "", f"Source character offsets: [{ev['start']}, {ev['end']}).", ""]
            if "judgment_reuse" in row:
                appendix += [f"Exact-content decision reused under the same query from `{row['judgment_reuse']['source_doc_id']}`.", ""]
    (ROOT / "reports/CUSTOM_20_DEPTH20_EVIDENCE.md").write_text("\n".join(appendix), encoding="utf-8")
    print(json.dumps({"assessed_pairs": len(labels), "quality": quality, "truncated_pairs": visibility["truncated_pairs"]}, indent=2))


if __name__ == "__main__":
    main()

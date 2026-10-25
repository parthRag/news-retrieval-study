"""Regenerate hybrid/pilot reports, figures and exact E5 evidence-visibility audit.

This script validates and reports existing manual AI decisions. It assigns no grades.
"""

import json
import os
from collections import Counter
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("artifacts/plot-cache").resolve()))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from news_ir.assessment import assessed_top5_metrics, validate_assessments
from news_ir.data import sha256_file


ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "artifacts/assessments/custom20-v1"
LABELS = ROOT / "annotations/ai_study_v1/assessments.pilot.jsonl"
EVALUATION = ROOT / "artifacts/evaluations/rrf-original-57"
FIGURES = ROOT / "reports/figures/current-study"
NAMES = {"bm25": "BM25", "dense": "E5 dense", "rrf": "RRF hybrid"}
COLORS = ["#3477a8", "#d97a29", "#368b65"]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def figures(metrics, pilot):
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), constrained_layout=True)
    for ax, metric, label in zip(axes, ["ndcg_at_5", "ap_at_1000"], ["nDCG@5 (linear gain)", "MAP@1000"]):
        values = [metrics["primary"][e]["aggregate"][metric] for e in NAMES]
        bars = ax.bar(list(NAMES.values()), values, color=COLORS, width=.6)
        ax.bar_label(bars, fmt="%.4f", padding=4)
        ax.set(title=label, ylabel="Macro mean over original 57 queries", ylim=(0, .62))
        ax.spines[["top", "right"]].set_visible(False)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(FIGURES / f"original_57_three_engines.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)
    fig, axes = plt.subplots(1, len(pilot["query_ids"]), figsize=(8, 3.5), squeeze=False, constrained_layout=True)
    for ax, qid in zip(axes.flat, pilot["query_ids"]):
        values = [pilot["per_query"][qid][e]["ndcg_at_5"] for e in ("bm25", "dense")]
        bars = ax.bar(["BM25", "E5 dense"], values, color=COLORS[:2], width=.55)
        ax.bar_label(bars, fmt="%.3f", padding=3)
        ax.set(title=qid + (": negation" if qid == "N03" else ": cricket food"),
               ylabel="Pilot nDCG@5 (AI labels)", ylim=(0, 1.15))
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Pilot only: {pilot['query_count']} of 20 queries; assessed-pool ideal ranking", fontsize=11)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(FIGURES / f"ai_pilot_two_queries.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def visibility_audit(labels, *, scope="pilot"):
    from transformers import AutoTokenizer
    from news_ir.embedding import read_model_spec

    model = ROOT / "artifacts/models/e5-base-v2"
    spec = read_model_spec(model)
    tokenizer = AutoTokenizer.from_pretrained(str(model), local_files_only=True, trust_remote_code=False)
    articles = {(r["query_id"], r["doc_id"]): r for r in
                map(json.loads, (POOL / "articles.blinded.jsonl").read_text().splitlines())}
    documents = []
    for row in labels:
        article = articles[row["query_id"], row["doc_id"]]
        contents = (article["title"] + "\n" + article["text"]).strip()
        prefixed = spec["passage_prefix"] + contents
        offsets = tokenizer(prefixed, truncation=True, max_length=spec["max_length"],
                            return_offsets_mapping=True)["offset_mapping"]
        visible_end = max(0, max(end for _, end in offsets) - len(spec["passage_prefix"]))
        documents.append({"query_id": row["query_id"], "doc_id": row["doc_id"], "title": article["title"],
                          "grade": row["grade"], "contents_sha256": row["contents_sha256"],
                          "body_characters": len(article["text"]), "contents_characters": len(contents),
                          "retained_contents_end_exclusive": visible_end,
                          "truncated": visible_end < len(contents), "empty_body": not article["text"].strip(),
                          "evidence": [{**span, "fully_visible_to_e5": span["end"] <= visible_end}
                                       for span in row["evidence"]]})
    counts = Counter(d["contents_sha256"] for d in documents)
    return {"model_revision": spec["revision"], "tokenizer_sha256": sha256_file(model / "tokenizer.json"),
            "passage_prefix": spec["passage_prefix"], "total_token_budget": spec["max_length"],
            "scope": f"{len(labels)} assessed {scope} pairs only; no new model inference or relevance decisions",
            "interpretation": "Visibility concerns exact retained input text, not model attention or a causal explanation of scores",
            "documents": documents, "empty_body_pairs": sum(d["empty_body"] for d in documents),
            "truncated_pairs": sum(d["truncated"] for d in documents),
            "duplicate_content_hashes": {digest: count for digest, count in counts.items() if count > 1}}


def main():
    validation = validate_assessments(POOL, LABELS)
    pilot = assessed_top5_metrics(POOL, LABELS)
    annotation = LABELS.parent
    dump(annotation / "metrics.pilot.json", pilot)
    dump(annotation / "validation.pilot.json", {k: v for k, v in validation.items() if k != "qrels"})
    labels = list(map(json.loads, LABELS.read_text().splitlines()))
    audit = visibility_audit(labels)
    dump(annotation / "evidence_visibility.pilot.json", audit)
    metrics = json.loads((EVALUATION / "metrics.json").read_text())
    paired = json.loads((EVALUATION / "paired_comparison.json").read_text())
    figures(metrics, pilot)

    lines = ["# Fixed reciprocal-rank fusion: original 57-query benchmark", "",
             "This exploratory extension combines the saved full-corpus BM25 and E5 top-1,000 rankings. "
             "It uses equal weights and **k=60**, with score `sum(1 / (60 + rank))`, retains the top 1,000 unique IDs, "
             "and breaks score ties by ascending document ID. No relevance labels, training, parameter search or additional GPU encoding were used.", "",
             "| Metric | BM25 | E5 dense | RRF hybrid |", "| --- | ---: | ---: | ---: |"]
    for key, name in (("ndcg_at_5", "nDCG@5, linear gains"), ("ap_at_1000", "MAP@1000"),
                      ("recall_at_1000", "Recall@1000"), ("precision_at_5", "P@5"), ("judged_at_5", "Judged fraction at 5")):
        lines.append("| " + name + " | " + " | ".join(f"{metrics['primary'][e]['aggregate'][key]:.6f}" for e in NAMES) + " |")
    lines += ["", "![Three-engine comparison](figures/current-study/original_57_three_engines.png)", "",
              "## Paired uncertainty", "", "Descriptive paired bootstrap over queries, 10,000 draws, seed 20261025. "
              "This is an exploratory third-system comparison, not a confirmatory new held-out experiment.", "",
              "| Difference | Measure | Mean | 95% percentile interval | Hybrid wins / ties / losses |",
              "| --- | --- | ---: | --- | --- |"]
    for baseline, comparisons in paired["comparisons"].items():
        for metric, values in comparisons.items():
            lo, hi = values["paired_bootstrap_95_percentile_ci"]
            lines.append(f"| RRF − {NAMES[baseline]} | {metric} | {values['mean_difference']:+.6f} | "
                         f"[{lo:+.6f}, {hi:+.6f}] | {values['rrf_wins']} / {values['ties']} / {values['baseline_wins']} |")
    lines += ["", "The hybrid has higher means, but its nDCG@5 interval against E5 includes zero. "
              "The AP difference intervals against both baselines exclude zero under this descriptive bootstrap. "
              "Incomplete and unequal judgment coverage still limits interpretation.", "",
              "## Sensitivity and validation", "", "| Gain/policy | BM25 nDCG@5 | E5 nDCG@5 | RRF nDCG@5 |",
              "| --- | ---: | ---: | ---: |"]
    for policy, values in metrics.items():
        lines.append("| " + policy + " | " + " | ".join(f"{values[e]['aggregate']['ndcg_at_5']:.6f}" for e in NAMES) + " |")
    lines += ["", "All **1,624** additional RRF comparisons against independent native `trec_eval` passed across four policies. "
              "Derived ordinal scores preserve published rank order during cross-checking. The original 57-query baselines reproduce exactly. "
              "All original qrels, queries and engine rankings are preserved. These are original background-linking results, "
              "not results on the custom linguistic stress queries.", "",
              "Fusion averages about **0.69 ms/query over saved rankings** on this run. This excludes both searches, startup, "
              "file loading and article lookup; it is not end-to-end hybrid latency. Live hybrid search still incurs both engines' costs. "
              "No extra vector index is required; the existing BM25 and dense index folders occupy approximately 367.6 MiB "
              "and 1.72 GiB on disk, respectively. Disk size is not peak RAM.", "",
              "## Reproduce", "", "```sh", ".venv/bin/news-ir fuse --output artifacts/runs/rrf-original-k60-new",
              ".venv/bin/python scripts/evaluate_fusion.py --fusion-run artifacts/runs/rrf-original-k60-new --output artifacts/evaluations/rrf-original-57-new",
              ".venv/bin/python scripts/report_current_study.py", "```", "",
              "The report script reads the canonical saved evaluation. Evaluation and retrieval commands refuse to overwrite existing outputs.", "",
              "Method reference: [Cormack, Clarke and Buettcher, SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).", ""]
    (ROOT / "reports/RRF_EXPERIMENT.md").write_text("\n".join(lines))

    lookup = {(r["query_id"], r["doc_id"]): r for r in labels}
    protocol = json.loads((POOL / "protocol.json").read_text())
    queries = {r["_id"]: r for r in map(json.loads, (POOL / "queries.jsonl").read_text().splitlines())}
    lines = ["# Custom query AI assessment: calibration pilot", "",
             "**Two of 20 queries, 16 of 737 pooled pairs assessed.** The assistant read every available title and full body "
             "for these 16 records and stored a grade, confidence, rationale, exact source quotations and character offsets. "
             "Two records have empty bodies: full reading means all available corpus content, not recovery of missing original text. "
             "These full-article AI judgments support a preliminary comparison; human review is planned next ([review plan](ASSESSMENT_METHOD.md)).", "",
             "The user explicitly authorized assistant assessment. The fixed 20-query wording, rubric and inclusive event windows "
             "are copied byte-for-byte from the pre-existing draft. Historical draft/human-review status remains in that source snapshot; "
             "the new protocol authorizes AI assessment. Human approval fields are blank. "
             "The protocol was recorded after retrieval and initial H01 inspection, so no preregistration or perfect assessor blindness is claimed.", "",
             "The equal-depth pool unions top 20 from each full-corpus engine: **737 pairs**, with **188** in either top five. "
             "Article packets omit engine/rank/score and use deterministic hash order. All stored evidence spans validate exactly "
             "against their article hashes. Unresolved judgments remain unassessed rather than becoming grade 0.", "",
             "| Query | BM25 nDCG@5 | E5 nDCG@5 | BM25 P@5 | E5 P@5 |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for qid in pilot["query_ids"]:
        row = pilot["per_query"][qid]
        lines.append(f"| {qid} | {row['bm25']['ndcg_at_5']:.6f} | {row['dense']['ndcg_at_5']:.6f} | "
                     f"{row['bm25']['precision_at_5']:.2f} | {row['dense']['precision_at_5']:.2f} |")
    lines += ["", "Both engines have 100% assessed top-five coverage for these two queries. Primary nDCG uses linear 0–2 gains; "
              "the ideal ranking is drawn from assessed positives and can change with deeper assessment. "
              "The earlier blueprint proposed exp2 gains; current primary gains align with the original benchmark, "
              "and exp2 sensitivity is also saved in `metrics.pilot.json`. "
              "**MAP is withheld while the designated pool remains incomplete.** A two-query pilot average is not a 20-query result.", "",
              "![AI pilot](figures/current-study/ai_pilot_two_queries.png)", ""]
    for qid in pilot["query_ids"]:
        lines += [f"## {qid}: {queries[qid]['text']}", "", "| Engine | Rank | Grade | Article ID |", "| --- | ---: | ---: | --- |"]
        for engine in ("bm25", "dense"):
            run = Path(protocol["runs"][engine]["path"])
            row = next(r for r in map(json.loads, (run / "results.jsonl").read_text().splitlines()) if r["query_id"] == qid)
            for hit in row["hits"][:5]:
                lines.append(f"| {NAMES[engine]} | {hit['rank']} | {lookup[qid, hit['doc_id']]['grade']} | `{hit['doc_id']}` |")
        if qid == "H01":
            lines += ["", "**Observed:** E5 retrieves cricket-food reporting throughout its top five. BM25's ranks 3–4 instead "
                      "discuss organic/conventional crops and oats. Their farming, environmental and nutrition vocabulary fits parts "
                      "of the query but the mandatory cricket-food entity is missing. Two E5 articles receive only grade 1 "
                      "because their nutrition/environmental support is brief or generic. This is an observed topic-focus difference, "
                      "not proof of an internal reasoning mechanism.", ""]
        else:
            lines += ["", "**Observed:** BM25 retrieves four articles with explicit requested negative statements plus contact explanations, "
                      "but its rank-one article fails that constraint. E5 puts an opposite-polarity headline stub first and two "
                      "one-word, empty-body `ebola` records second and third; those two IDs have identical available content. "
                      "Its fourth result satisfies the need, while its fifth is the same failing article as BM25 rank one. "
                      "This mixes constraint failure, sparse content and duplicate content; it does not isolate negation as the sole cause. "
                      "Grade 0 means failure to satisfy this information need, not a judgment about current medical truth.", ""]
    lines += ["## Evidence visibility and next experiments", "",
              f"The exact local tokenizer audit finds **{audit['truncated_pairs']} of 16** pilot records are truncated by the "
              f"512-token E5 budget and **{audit['empty_body_pairs']}** have empty bodies. "
              "`annotations/ai_study_v1/evidence_visibility.pilot.json` records whether each saved evidence span is wholly visible "
              "in the actual passage-prefixed input. This measures input availability, not attention or causal importance.", "",
              "Next: complete top-five judgments for the remaining 18 queries, then assess the remaining depth-20 pool "
              "and evaluate pooled MAP@1000 with coverage disclosures. Keep the same wording regardless of which engine wins. "
              "Useful later ablations are constraint-flip query pairs, removal of empty/near-empty records for both engines, "
              "content deduplication, and passage coverage. Each needs separate runs and compatible labels; none is silently applied to these baselines.", "",
              "AI-assessment limitation: [Ian Soboroff (2025), Don't Use LLMs to Make Relevance Judgments](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958495). "
              "Assistant labels enable an exploratory study but do not establish human agreement or unbiased system preference.", ""]
    (ROOT / "reports/CUSTOM_AI_PILOT.md").write_text("\n".join(lines))
    print(json.dumps({"hybrid_report": "reports/RRF_EXPERIMENT.md", "pilot_report": "reports/CUSTOM_AI_PILOT.md",
                      "validated_assessments": validation["assessed_pairs"], "tokenizer_audited_pairs": len(audit["documents"]),
                      "figures": str(FIGURES)}, indent=2))


if __name__ == "__main__":
    main()

"""Generate paper figures, per-query comparisons and evidence for the original 57 topics."""

import csv
import json
import os
from collections import Counter
from pathlib import Path

# Keep plotting's font/config cache in the writable project directory.
os.environ.setdefault("MPLCONFIGDIR", str(Path("artifacts/plot-cache").resolve()))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from news_ir.data import DocumentStore, sha256_file
from news_ir.evaluation import load_qrels


ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "artifacts/evaluations/original-57"
FIGURES = ROOT / "reports/figures/original-57"
ANALYSIS = ROOT / "artifacts/analysis/original-57"
COLORS = {"bm25": "#3477a8", "dense": "#d97a29"}


def save_figure(fig, name):
    for suffix in ("svg", "pdf", "png"):
        fig.savefig(FIGURES / f"{name}.{suffix}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_figures(metrics, rows):
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.4), constrained_layout=True)
    for ax, metric, label in zip(axes, ("ndcg_at_5", "ap_at_1000"), ("nDCG@5 (linear gain)", "MAP@1000")):
        values = [metrics[e]["aggregate"][metric] for e in ("bm25", "dense")]
        bars = ax.bar(["BM25", "E5 dense"], values, color=list(COLORS.values()), width=0.55)
        ax.bar_label(bars, fmt="%.4f", padding=4)
        ax.set_ylim(0, max(values) * 1.25)
        ax.set_title(label)
        ax.set_ylabel("Macro mean over 57 queries")
        ax.spines[["top", "right"]].set_visible(False)
    save_figure(fig, "aggregate_scores")
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), constrained_layout=True)
    for ax, metric, label in zip(axes, ("ndcg_at_5", "ap_at_1000"), ("nDCG@5", "AP@1000")):
        ax.scatter([float(r[f"bm25_{metric}"]) for r in rows], [float(r[f"dense_{metric}"]) for r in rows],
                   s=24, color=COLORS["dense"], alpha=0.75)
        ax.plot([0, 1], [0, 1], color="gray", linestyle="--", linewidth=1)
        ax.set(xlim=(-0.02, 1.02), ylim=(-0.02, 1.02), xlabel=f"BM25 {label}", ylabel=f"E5 {label}")
        ax.set_aspect("equal")
        ax.spines[["top", "right"]].set_visible(False)
    save_figure(fig, "paired_query_scores")
    ordered = sorted(rows, key=lambda r: float(r["delta_ndcg_at_5"]))
    fig, ax = plt.subplots(figsize=(13, 3.8), constrained_layout=True)
    values = [float(r["delta_ndcg_at_5"]) for r in ordered]
    ax.bar([r["query_id"] for r in ordered], values, color=[COLORS["dense"] if v > 0 else COLORS["bm25"] for v in values])
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set(xlabel="Original query ID (sorted by difference)", ylabel="E5 minus BM25 nDCG@5")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    save_figure(fig, "per_query_ndcg_difference")
    fig, ax = plt.subplots(figsize=(7, 3.5), constrained_layout=True)
    for offset, engine in enumerate(("bm25", "dense")):
        values = [metrics[engine]["aggregate"][f"judged_at_{k}"] for k in (5, 20, 1000)]
        ax.bar([n + (offset - 0.5) * 0.34 for n in range(3)], values, width=0.34,
               label="BM25" if engine == "bm25" else "E5 dense", color=COLORS[engine])
    ax.set_xticks(range(3), ["Top 5", "Top 20", "Top 1000"])
    ax.set(ylim=(0, 1.05), ylabel="Fraction with an existing judgment")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    save_figure(fig, "judged_coverage")


def case_evidence(rows):
    """Select actual largest gains/losses; never invent a balanced outcome."""
    positive = sorted((r for r in rows if float(r["delta_ndcg_at_5"]) > 0), key=lambda r: -float(r["delta_ndcg_at_5"]))[:2]
    negative = sorted((r for r in rows if float(r["delta_ndcg_at_5"]) < 0), key=lambda r: float(r["delta_ndcg_at_5"]))[:2]
    runs = {engine: {r["query_id"]: r for r in [json.loads(line) for line in (ROOT / path / "results.jsonl").read_text().splitlines()]}
            for engine, path in (("bm25", "artifacts/runs/bm25-original-benchmark"), ("dense", "artifacts/runs/dense-original"))}
    queries = [json.loads(line) for line in (ROOT / "queries.jsonl").read_text().splitlines()]
    qrels = load_qrels(ROOT / "qrel.jsonl", [q["_id"] for q in queries])
    from news_ir.runtime import initialize_jvm
    initialize_jvm()
    from pyserini.analysis import Analyzer, get_lucene_analyzer
    from transformers import AutoTokenizer
    analyzer = Analyzer(get_lucene_analyzer(stemming=False, stopwords=False))
    tokenizer = AutoTokenizer.from_pretrained(str(ROOT / "artifacts/models/e5-base-v2"),
                                             local_files_only=True, trust_remote_code=False)
    cases = []
    with DocumentStore(ROOT / "artifacts/indexes/bm25") as store:
        for row in positive + negative:
            qid = row["query_id"]
            evidence = {"query_id": qid, "query": row["query"], "delta_ndcg_at_5": float(row["delta_ndcg_at_5"]),
                        "bm25_ndcg_at_5": float(row["bm25_ndcg_at_5"]), "dense_ndcg_at_5": float(row["dense_ndcg_at_5"]), "engines": {}}
            for engine in ("bm25", "dense"):
                documents = []
                for hit in runs[engine][qid]["hits"][:5]:
                    doc = store.get(hit["doc_id"])
                    prefixed = "passage: " + doc.contents
                    offsets = tokenizer(prefixed, truncation=True, max_length=512, return_offsets_mapping=True)["offset_mapping"]
                    retained = prefixed[len("passage: "):max(end for _, end in offsets)]
                    full_counts, prefix_counts = Counter(analyzer.analyze(doc.contents)), Counter(analyzer.analyze(retained))
                    tokens = list(dict.fromkeys(analyzer.analyze(row["query"])))
                    documents.append({**hit, "title": doc.title, "grade": qrels[qid].get(doc.doc_id),
                                      "judgment_status": "judged" if doc.doc_id in qrels[qid] else "unjudged",
                                      "opening_evidence": doc.text[:1000], "full_body_characters": len(doc.text),
                                      "e5_retained_text": retained,
                                      "query_token_counts_full": {t: full_counts[t] for t in tokens},
                                      "query_token_counts_e5_prefix": {t: prefix_counts[t] for t in tokens}})
                evidence["engines"][engine] = documents
            cases.append(evidence)
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    (ANALYSIS / "case_evidence.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n")
    lines = ["# Original benchmark: measured case studies", "",
             "Cases are the two largest positive and two largest negative E5-minus-BM25 nDCG@5 differences. "
             "Grades come from the original qrels; **unjudged is not a verified grade 0**. "
             "Opening passages provide inspection evidence, not automatic rationales or explanations of neural reasoning.", ""]
    for case in cases:
        lines += [f"## Query {case['query_id']}: {case['query']}", "",
                  f"BM25 nDCG@5: **{case['bm25_ndcg_at_5']:.4f}**; E5: **{case['dense_ndcg_at_5']:.4f}**; "
                  f"E5 minus BM25: **{case['delta_ndcg_at_5']:+.4f}**.", "",
                  "| Engine | Rank | Supplied grade | Article |", "| --- | ---: | ---: | --- |"]
        for engine, docs in case["engines"].items():
            for doc in docs:
                grade = "Unjudged" if doc["grade"] is None else str(doc["grade"])
                title = doc["title"].replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {'BM25' if engine=='bm25' else 'E5'} | {doc['rank']} | {grade} | {title} |")
        for engine in ("bm25", "dense"):
            doc = case["engines"][engine][0]
            excerpt = " ".join(doc["opening_evidence"].split())[:650]
            lines += ["", f"**{'BM25' if engine=='bm25' else 'E5'} rank-one evidence** (`{doc['doc_id']}`):", "", "> " + excerpt, ""]
        notes = {
            "870": "BM25's five leading results are all judged 0 and focus on politics, transgender policy or Sessions. "
                   "Its leading article mentions Sessions and transgender military service while omitting killing-related language in the inspected body. "
                   "E5 instead retrieves reporting about killings and violence, beginning with a grade-4 article that does not name Sessions. "
                   "This is consistent with entity-focused lexical distraction versus retrieval of the central event, "
                   "but does not prove an internal neural reasoning mechanism.",
            "830": "E5 connects the query's 'small enough to sit on a fingernail' description with a grade-4 article about 'miniature frogs'. "
                   "BM25's leading bat-titled article also discusses frog discoveries extensively in its body, so the lexical result is not explained by the headline alone. "
                   "The measured grades distinguish the background links; a plausible explanation is better matching of the size/species concept by E5. "
                   "Exact query-token counts for full text and the E5 prefix are saved in the evidence JSON.",
            "852": "BM25 receives its advantage from grades 3/2/2/2 at ranks 2–5, while both systems' rank-one articles are judged 0. "
                   "Three of E5's top-five articles are unjudged and contribute zero under the declared convention. "
                   "Its top article discusses a different FDA nicotine plan. This example mixes a measured focus mismatch with incomplete judgment coverage; "
                   "the unjudged articles cannot be called confirmed semantic failures. "
                   "The three grade-2 BM25 articles also have very similar opening text; near-duplicate suppression was not applied, "
                   "so this result does not establish an advantage in information diversity.",
            "827": "All five BM25 results are positively judged, including a grade-4 document at rank five; E5 has an unjudged rank-one article and lower-graded positive links. "
                   "The BM25 lead is a 30,729-character investigation of DEA enforcement and distributors, while E5's lead is a shorter editorial using the alternate term 'wholesalers'. "
                   "Both are topically connected, so lexical specificity, article coverage and incomplete judgments are competing explanations. "
                   "This result does not establish that E5 failed to understand the opioid topic.",
        }
        if case["query_id"] in notes:
            lines += ["**Observed pattern and interpretation:** " + notes[case["query_id"]], ""]
    lines += ["## Interpretation limits", "",
              "These headline/background-linking results support a diagnosis of topic focus and judgment coverage. "
              "They do not test whether either system obeys the 20 custom negation, homonym or temporal constraints. "
              "Article-level excerpts cannot establish why E5 assigned a score. Full-body versus 512-token input coverage "
              "and incomplete judgments remain competing explanations.", ""]
    (ROOT / "reports/ORIGINAL_57_CASE_STUDIES.md").write_text("\n".join(lines))
    return cases


def main():
    metrics = json.loads((EVALUATION / "metrics.json").read_text())
    manifest = json.loads((EVALUATION / "manifest.json").read_text())
    paired = json.loads((EVALUATION / "paired_comparison.json").read_text())
    with (EVALUATION / "per_query.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    make_figures(metrics["primary"], rows)
    cases = case_evidence(rows)
    lines = ["# Original 57-query benchmark: BM25 versus E5 dense retrieval", "",
             "Completed on 24 October 2026. Both engines retrieved the top 1,000 articles for each original query "
             "from the same **594,589-document** corpus. Evaluation uses all **15,655 supplied judgments**. "
             "This is the original headline/background-linking benchmark; the separate 20-query challenge suite remains deferred.", "",
             "## Main results", "", "| Metric | BM25 | E5 dense | E5 minus BM25 |", "| --- | ---: | ---: | ---: |"]
    names = (("ndcg_at_5", "nDCG@5, direct-grade gain"), ("ndcg_at_10", "nDCG@10, direct-grade gain"),
             ("ap_at_1000", "MAP@1000"), ("recall_at_1000", "Recall@1000"),
             ("precision_at_5", "Precision@5"), ("reciprocal_rank_at_1000", "MRR@1000"))
    for key, label in names:
        b, d = (metrics["primary"][e]["aggregate"][key] for e in ("bm25", "dense"))
        lines.append(f"| {label} | {b:.6f} | {d:.6f} | {d-b:+.6f} |")
    lines += ["", "E5 has higher averages on this query set, while performance varies by query. "
              "These measurements do not establish that dense retrieval always outperforms BM25 or that every LLM has these capabilities.", "",
              "![Aggregate scores](figures/original-57/aggregate_scores.svg)", "",
              "## Paired query analysis", "",
              "| Metric | Dense wins | Ties | BM25 wins | Mean difference | Paired bootstrap 95% interval |",
              "| --- | ---: | ---: | ---: | ---: | --- |"]
    for key, label in (("ndcg_at_5", "nDCG@5"), ("ap_at_1000", "AP@1000")):
        x = paired["metrics"][key];low, high = x["paired_bootstrap_95_percentile_ci"]
        lines.append(f"| {label} | {x['dense_wins']} | {x['ties']} | {x['bm25_wins']} | {x['mean_dense_minus_bm25']:+.6f} | [{low:+.6f}, {high:+.6f}] |")
    lines += ["", "Intervals use 10,000 paired query resamples with seed 20261024. "
              "The nDCG@5 interval includes zero; its average advantage is uncertain at this interval level. "
              "The AP difference interval is positive for this resampling analysis. These are descriptive percentile intervals, "
              "conditional on the supplied judgments and query-independence assumption, rather than broad population guarantees.", "",
              "![Paired query scores](figures/original-57/paired_query_scores.svg)", "",
              "![Per-query differences](figures/original-57/per_query_ndcg_difference.svg)", "",
              "## Evaluation definitions", "",
              "The primary nDCG gain equals the supplied relevance grade (0–4), with discount `1/log2(rank+1)`. "
              "The ideal ranking uses every original judgment, including unavailable positive documents. "
              "This direct-grade convention follows [BEIR's evaluator](https://github.com/beir-cellar/beir/blob/main/beir/retrieval/evaluation.py) "
              "and [trec_eval's ndcg_cut implementation](https://github.com/usnistgov/trec_eval/blob/main/m_ndcg_cut.c).", "",
              "AP treats grade > 0 as relevant, sums precision at each relevant hit within the 1,000 saved ranks, "
              "and divides by **all** known relevant articles for that query. MAP@1000 is the macro mean over all 57 queries. "
              "Unjudged articles contribute zero gain/relevance while retaining their rank positions; this convention "
              "does not establish that they are actually irrelevant. See [trec_eval's map_cut definition](https://github.com/usnistgov/trec_eval/blob/main/m_map_cut.c).", "",
              "## Sensitivity to gain convention and unavailable articles", "",
              "| Policy | BM25 nDCG@5 | E5 nDCG@5 | BM25 MAP@1000 | E5 MAP@1000 |", "| --- | ---: | ---: | ---: | ---: |"]
    for key, label in (("primary", "Primary: supplied grades, all qrels"), ("exp2_gain", "Gain 2^grade - 1, all qrels"),
                       ("news2019_gain", "Original NIST gains 0/2/4/8/16"), ("available_corpus", "Available-corpus sensitivity, linear gain")):
        b, d = (metrics[key][e]["aggregate"] for e in ("bm25", "dense"))
        lines.append(f"| {label} | {b['ndcg_at_5']:.6f} | {d['ndcg_at_5']:.6f} | {b['ap_at_1000']:.6f} | {d['ap_at_1000']:.6f} |")
    lines += ["", f"There are **{manifest['unavailable_judgments']} judgments** referring to "
              f"**{manifest['unavailable_unique_documents']} unique unavailable articles**, including "
              f"**{manifest['unavailable_positive_judgments']} positive judgments**. The primary results retain them. "
              "The available-corpus row removes only those judgments from the reference set and reuses the exact same rankings.", "",
              "## Judgment coverage", "", "| Retrieved slice | BM25 judged | E5 judged |", "| --- | ---: | ---: |"]
    for cutoff in (5, 10, 20, 1000):
        b, d = (metrics["primary"][e]["aggregate"][f"judged_at_{cutoff}"] for e in ("bm25", "dense"))
        lines.append(f"| Top {cutoff} | {b:.2%} | {d:.2%} |")
    lines += ["", "E5's top-ranked results have lower existing judgment coverage. An unjudged result may be useful, "
              "so these metrics measure performance against this incomplete reference set. "
              "This particularly limits strong failure claims based on E5's unjudged articles.", "",
              "![Judged coverage](figures/original-57/judged_coverage.svg)", "",
              "## Provenance and independent verification", "",
              "All 15,655 query-document pairs match the [official NIST qrels](https://trec.nist.gov/data/news/2019/newsir19-qrels-background.txt). "
              "The supplied grade mapping is 0 → 0 and positive grade g → 2^g in NIST's gain-valued file. "
              "Official topic metadata has 60 topics, of which the supplied 57 have judgments here. "
              "None of their canonical source articles occurs in the local corpus. "
              "The topic/grade audit is recorded in `artifacts/original_benchmark_provenance.json`; see the [NIST data page](https://trec.nist.gov/data/news2019.html).", "",
              "The native trec_eval implementation bundled with Anserini independently checks all per-query and aggregate "
              "nDCG@5/10, MAP@1000, Recall@1000, Precision@5/10 and reciprocal-rank values for both engines "
              "under all four policies. Agreement tolerance is 0.000051 because native output is rounded to four decimals. "
              "A derived ordinal-score run preserves the submitted rank order when native trec_eval resolves ties; "
              "the original model scores and runs are preserved. Hand-calculated fixtures, empty-query behavior, "
              "missing-positive denominators, invalid-label rejection and atomic publication are also tested.", "",
              "## Measured examples", "", "| Query | Short description | BM25 nDCG@5 | E5 nDCG@5 |", "| --- | --- | ---: | ---: |"]
    for case in cases:
        lines.append(f"| {case['query_id']} | {case['query'].replace('|', '/')} | {case['bm25_ndcg_at_5']:.4f} | {case['dense_ndcg_at_5']:.4f} |")
    lines += ["", "See [ORIGINAL_57_CASE_STUDIES.md](ORIGINAL_57_CASE_STUDIES.md) for the top-five articles, supplied grades "
              "and source excerpts. These are selected extreme cases, not a representative random sample.", "",
              "## Scope and limitations", "",
              "- This is the downloaded headline/background-linking adaptation; it is not the 20-query linguistic stress study or a full official TREC reproduction.",
              "- BM25 reads full article bodies. E5 receives the beginning within 512 total tokens, including its prefix and special tokens. This input-coverage difference is a confound.",
              "- No publication-date or near-duplicate-cluster filters were implemented. The corpus lacks the metadata needed to reproduce all original task rules reliably.",
              "- Fixed BM25/model settings were evaluated without tuning on these qrels. No relevance labels were generated or changed.",
              "- Both runs used the local Mac, but retrieval overlapped development/testing and memory pressure on an 8 GiB machine. Saved latencies are operational observations, not a controlled speed comparison.",
              "- Higher aggregate scores do not demonstrate robustness to negation, ambiguous senses or explicit temporal constraints. Those claims require the deferred custom study.", "",
              "## Reproduce and inspect", "", "```sh",
              ".venv/bin/news-ir run --queries queries.jsonl --output artifacts/runs/bm25-original-reproduced --top-k 1000",
              ".venv/bin/news-ir run --engine dense --queries queries.jsonl --output artifacts/runs/dense-original-reproduced --top-k 1000 --device cpu",
              ".venv/bin/news-ir evaluate --bm25-run artifacts/runs/bm25-original-reproduced --dense-run artifacts/runs/dense-original-reproduced --output artifacts/evaluations/original-57-reproduced",
              ".venv/bin/python scripts/report_original_benchmark.py", "```", "",
              "Existing run/evaluation directories are never silently overwritten. "
              "The report script regenerates figures and report text from `artifacts/evaluations/original-57/`.", "",
              "Machine-readable results: `metrics.json`, `per_query.csv`, `paired_comparison.json`, "
              "`crosscheck.json`, `unavailable_judgments.json` and `manifest.json` in that evaluation directory. "
              "Standalone SVG, PDF and PNG plots are under `reports/figures/original-57/`.", ""]
    (ROOT / "reports/ORIGINAL_57_BENCHMARK.md").write_text("\n".join(lines))
    print("Generated reports/ORIGINAL_57_BENCHMARK.md, case evidence and 12 standalone figure files.")


if __name__ == "__main__":
    main()

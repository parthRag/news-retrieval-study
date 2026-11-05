"""Build an exportable chart and readable interpretation of frozen diagnostics."""
import argparse
import json
import os
import tempfile
from pathlib import Path

from news_ir.data import sha256_file
from analyze_complementarity import ROOT, write


def findings(summaries, stability):
    title, rewrite = summaries["core18/title"], summaries["core18/rewrite"]
    covid, covid_b = summaries["covid/original"], summaries["covid/rewrite_b"]
    d = title["depths"]["20"]
    stable = stability["core18"]["rewrite"]
    return "\n".join([
        "## Findings and next implementation step", "",
        f"**The engines contribute different useful candidates.** On Core 2018 titles, the top-20 lists share a mean Jaccard of only {d['jaccard']:.3f}. BM25 finds {d['bm25_only_known_relevant']:.2f} known-positive records per query outside E5's top 20; E5 finds {d['dense_only_known_relevant']:.2f} outside BM25's top 20. This supports retaining both candidate generators rather than replacing one based on its aggregate score.", "",
        f"**Candidate availability and ranking quality are different problems.** For Core titles, RRF achieves {title['engines']['rrf']['ndcg_at_5']:.4f} nDCG@5, whereas the label-informed ideal ordering of the top-20 union reaches {d['oracle_union_ndcg_at_5']:.4f}. That gap shows that many high-grade articles are already candidates. It motivates a later reranking experiment; it does not promise that a real reranker can attain the ceiling. The union contains up to 40 records per topic and uses the known incomplete qrels.", "",
        f"**Fusion rescues individual articles without guaranteeing a better average.** For Core titles, {title['fusion_known_relevant_from_below_both_top5']} known-positive query–article pairs enter RRF's top five from below both source top fives. Yet its mean nDCG@5 is essentially tied with BM25 ({title['engines']['rrf']['ndcg_at_5']:.4f} versus {title['engines']['bm25']['ndcg_at_5']:.4f}). It improves {title['fusion_vs_source']['bm25']['wins']} topics, worsens {title['fusion_vs_source']['bm25']['losses']}, and ties on {title['fusion_vs_source']['bm25']['ties']}. The averages conceal meaningful per-topic tradeoffs.", "",
        f"**E5 preserves more of its ranking under provisional news rewrites.** Its original-to-rewrite top-10 Jaccard is {stable['dense']['10']['aggregate']['jaccard']:.3f}, compared with BM25's {stable['bm25']['10']['aggregate']['jaccard']:.3f}; mean prefix overlap is {stable['dense']['10']['aggregate']['mean_prefix_overlap']:.3f} versus {stable['bm25']['10']['aggregate']['mean_prefix_overlap']:.3f}. RRF's rewrite nDCG@5 is {rewrite['engines']['rrf']['ndcg_at_5']:.4f}, close to its title value of {title['engines']['rrf']['ndcg_at_5']:.4f}, even though the actual result membership changes. These are conditional robustness findings while human intent review is deferred.", "",
        f"**Hybrid is not a universal winner.** On original COVID queries, RRF scores {covid['engines']['rrf']['ndcg_at_5']:.4f}, even above the per-query engine-selector oracle's {covid['per_query_best_single_oracle_ndcg_at_5']:.4f}: fusion can create a useful ordering neither source supplied. On COVID rewrite B, however, RRF ({covid_b['engines']['rrf']['ndcg_at_5']:.4f}) is below E5 ({covid_b['engines']['dense']['ndcg_at_5']:.4f}). The paired interval includes zero, so this is a descriptive reversal, not evidence of a reliable dense advantage.", "",
        "The next retrieval experiment should rerank a fixed union of both engines' candidates, keeping these baselines frozen. A small cross-encoder would address ordering more directly than re-encoding the whole corpus. Before choosing weights or any learned selector, use held-out topics or nested validation; the label-informed oracle must never be presented as a tested selector. Human review is still needed for custom-label validation and rewrite intent, but it does not block implementing that experiment.", "",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "artifacts/evaluations/complementarity-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/analysis/complementarity-v1")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/COMPLEMENTARITY_DIAGNOSTICS.md")
    args = parser.parse_args()
    if args.output.exists() or args.report.exists():
        raise FileExistsError("Report/chart output exists; choose new paths")
    manifest = json.loads((args.input / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        if sha256_file(args.input / name) != digest:
            raise ValueError("Diagnostic output changed: " + name)
    summaries = json.loads((args.input / "summary.json").read_text(encoding="utf-8"))
    stability = json.loads((args.input / "formulation_stability.json").read_text(encoding="utf-8"))
    # Standard plotting tools; keep font caches outside the project data folders.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "news-ir-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    args.output.mkdir(parents=True)
    colors = {"bm25": "#b36a2e", "dense": "#2563a6", "rrf": "#187b66"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True)
    fig.subplots_adjust(left=.17, right=.99, bottom=.17, top=.78, wspace=.55)
    for ax, names, labels, title in [
        (axes[0], ["background/original", "core18/title", "core18/description", "core18/rewrite"],
         ["Background (57)", "Core titles (50)", "Core descriptions (50)", "Core rewrites* (50)"], "News: separate evaluation scopes"),
        (axes[1], ["covid/original", "covid/description", "covid/rewrite_a", "covid/rewrite_b"],
         ["Original (50)", "Descriptions (50)", "Rewrite A (50)", "Rewrite B (50)"], "COVID: same 50 topics, different formulations"),
    ]:
        for y, name in enumerate(names):
            row = summaries[name]
            for offset, engine in zip((-.14, 0, .14), ("bm25", "dense", "rrf"), strict=True):
                ax.scatter(row["engines"][engine]["ndcg_at_5"], y + offset, color=colors[engine], s=45, zorder=3)
            ax.scatter(row["depths"]["20"]["oracle_union_ndcg_at_5"], y, marker="D", s=40,
                       facecolors="none", edgecolors="#555555", zorder=3)
        ax.set_yticks(range(4), labels)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.03)
        ax.set_xlabel("Mean nDCG@5 (linear gains)")
        ax.set_title(title, fontsize=10, loc="left")
        ax.grid(axis="x", alpha=.22)
        ax.spines[["top", "right", "left"]].set_visible(False)
    handles = [Line2D([], [], marker="o", linestyle="none", color=c, label=n)
               for n, c in (("BM25", colors["bm25"]), ("E5", colors["dense"]), ("RRF", colors["rrf"]))]
    handles.append(Line2D([], [], marker="D", markerfacecolor="none", linestyle="none", color="#555555",
                          label="Top-20 union oracle (uses labels; up to 40 candidates)"))
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.55, .93), ncols=4, frameon=False, fontsize=8)
    fig.suptitle("Candidate complementarity leaves ranking headroom", fontsize=13, y=.99)
    fig.supxlabel("*Provisional news rewrites await human intent review. Oracle points are diagnostic ceilings, not achieved retrieval results.", fontsize=8, y=.015)
    for suffix in ("svg", "png"):
        fig.savefig(args.output / ("ranking_headroom." + suffix), dpi=180, bbox_inches="tight")
    plt.close(fig)
    source_report = (args.input / "REPORT.md").read_text(encoding="utf-8")
    insertion = source_report.index("## What was measured")
    # Relative report image URL follows the selected output location.
    relative = os.path.relpath(args.output / "ranking_headroom.svg", args.report.parent)
    report = (source_report[:insertion] + findings(summaries, stability) +
              f"![Engine scores and label-informed candidate ceilings]({relative})\n\n" + source_report[insertion:])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8", newline="\n")
    write(args.output / "manifest.json", {"diagnostic_manifest_sha256": sha256_file(args.input / "manifest.json"),
          "code_sha256": sha256_file(Path(__file__)), "report_sha256": sha256_file(args.report),
          "files": {p.name: sha256_file(p) for p in args.output.iterdir() if p.is_file()}})
    print(json.dumps({"report": str(args.report), "charts": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()

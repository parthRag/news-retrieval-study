"""Compiled trec_eval reference for Windows, where the Anserini binary is absent."""
import importlib.metadata
from types import SimpleNamespace

from .evaluation import gain


def windows_reference(qrels, rankings, measures, *, gain_mode="linear"):
    """Match trec_eval -q -c output and preserve empty-topic macro denominators.

    The calculations are from the separately compiled pytrec-eval-terrier
    extension, not the project's own metric implementation. Ordinal scores
    preserve published ranks, just as in the Java-wrapper cross-check.
    """
    try:
        import pytrec_eval
        version = importlib.metadata.version("pytrec-eval-terrier")
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        raise RuntimeError("Windows evaluation needs pytrec-eval-terrier; install the project's evaluation extra") from exc
    if not qrels or set(qrels) != set(rankings):
        raise ValueError("Reference evaluation needs identical nonempty query sets")
    labels = {q: {d: gain(g, gain_mode) for d, g in judgments.items()} for q, judgments in qrels.items()}
    runs = {q: {d: 1001 - rank for rank, d in enumerate(ids[:1000], 1)} for q, ids in rankings.items()}
    measures = set(measures)
    scores = pytrec_eval.RelevanceEvaluator(labels, measures).evaluate(runs)
    lines, aggregates = [], {m: 0.0 for m in measures}
    for q, ids in rankings.items():
        if ids and q not in scores:
            raise ValueError("Compiled evaluator omitted a nonempty query: " + q)
        for metric in sorted(measures):
            value = scores.get(q, {}).get(metric, 0.0)
            aggregates[metric] += value / len(qrels)
            # The native CLI omits per-query rows for empty rankings, while
            # retaining these topics at zero in its -c macro average.
            if ids:
                lines.append(f"{metric}\t{q}\t{value:.4f}")
    lines.extend(f"{metric}\tall\t{value:.4f}" for metric, value in sorted(aggregates.items()))
    return SimpleNamespace(stdout="\n".join(lines) + "\n",
                           version=f"pytrec-eval-terrier {version} (compiled trec_eval; Windows backend)")

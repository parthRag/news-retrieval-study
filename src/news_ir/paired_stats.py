"""Paired tests adapted from Hamsini G's controlled-rewrite study.

Source: robust-news-retrieval, commit 7b73bb339d9ea3827375ec10aa2e1c4bb67bde06,
src/stats.py. Original snapshot and provenance are under studies/. CLI and file
loading removed; topic pairing, percentile bootstrap, sign-flip test and Holm
procedures retained. These functions expect one independent observation per topic.
"""
from dataclasses import dataclass
import numpy as np

def qid_sort_key(qid):
    return (0, int(qid)) if qid.isdigit() else (1,qid)

@dataclass
class Comparison:
    run_a: str
    run_b: str
    measure: str
    n_topics: int
    mean_a: float
    mean_b: float
    mean_diff: float
    ci_low: float
    ci_high: float
    p_value: float
    p_holm: float
    wins: int
    ties: int
    losses: int


def paired_values(a: dict[str, dict[str, float]], b: dict[str, dict[str, float]], measure: str):
    if set(a) != set(b):
        raise ValueError(f"Runs cover different topics ({len(a)} vs {len(b)}); score them against the same qrels")
    qids = sorted(a, key=qid_sort_key)
    return np.array([a[q][measure] for q in qids]), np.array([b[q][measure] for q in qids])


def difference(x: dict[str, dict[str, float]], y: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Per-topic, per-measure x - y (e.g. a rewrite's score minus the original's)."""
    if set(x) != set(y):
        raise ValueError("Runs cover different topics; score them against the same qrels")
    return {q: {m: x[q][m] - y[q][m] for m in x[q] if m in y[q]} for q in x}


def load_scores(names: list[str], read) -> dict[str, dict]:
    """Per-topic scores for each name; "X-Y" is the per-topic difference of runs X and Y."""
    scores = {}
    for name in names:
        if "-" in name:
            x, y = name.split("-", 1)
            scores[name] = difference(read(x), read(y))
        else:
            scores[name] = read(name)
    return scores


def bootstrap_ci(diff: np.ndarray, n_resamples: int, alpha: float, rng: np.random.Generator) -> tuple[float, float]:
    """Percentile CI of the mean difference, resampling topics with replacement."""
    idx = rng.integers(0, len(diff), size=(n_resamples, len(diff)))
    means = diff[idx].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def randomization_p(diff: np.ndarray, n_resamples: int, rng: np.random.Generator) -> float:
    """Two-sided p-value: how often randomly swapping A/B per topic gives a mean
    difference at least as large as the observed one. (+1 so p is never 0.)"""
    observed = abs(diff.mean())
    signs = rng.choice([-1.0, 1.0], size=(n_resamples, len(diff)))
    extreme = np.sum(np.abs((signs * diff).mean(axis=1)) >= observed - 1e-12)
    return float((extreme + 1) / (n_resamples + 1))


def holm(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, returned in the input order."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def compare(scores: dict[str, dict], pairs: list[tuple[str, str]], measure: str,
            n_resamples: int = 10000, alpha: float = 0.05, seed: int = 42) -> list[Comparison]:
    """Test every pair; Holm correction is applied across the pairs given."""
    results = []
    for run_a, run_b in pairs:
        a, b = paired_values(scores[run_a], scores[run_b], measure)
        diff = a - b
        rng = np.random.default_rng(seed)  # same seed per pair: results don't depend on pair order
        low, high = bootstrap_ci(diff, n_resamples, alpha, rng)
        results.append(Comparison(
            run_a=run_a, run_b=run_b, measure=measure, n_topics=len(diff),
            mean_a=float(a.mean()), mean_b=float(b.mean()), mean_diff=float(diff.mean()),
            ci_low=low, ci_high=high, p_value=randomization_p(diff, n_resamples, rng), p_holm=0.0,
            wins=int(np.sum(diff > 0)), ties=int(np.sum(diff == 0)), losses=int(np.sum(diff < 0)),
        ))
    for result, adjusted in zip(results, holm([r.p_value for r in results])):
        result.p_holm = adjusted
    return results



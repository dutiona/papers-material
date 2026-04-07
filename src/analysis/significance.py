"""Statistical significance analysis for BEAM pilot results.

Bootstrap CIs on per-condition means and paired delta,
McNemar exact test on binarised correct/incorrect outcomes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

logger = logging.getLogger(__name__)


def bootstrap_ci(
    scores: np.ndarray,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Bootstrap percentile confidence interval for the mean."""
    rng = rng or np.random.default_rng(42)
    boot_means = np.array(
        [rng.choice(scores, size=len(scores), replace=True).mean() for _ in range(n_boot)]
    )
    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return lo, hi


def mcnemar_exact(
    typed_scores: np.ndarray, flat_scores: np.ndarray, threshold: float = 0.5
) -> dict:
    """McNemar exact test on binarised scores.

    Converts scores to binary (>threshold = correct), builds the 2x2
    contingency table, and runs the exact binomial test on discordant pairs.
    """
    typed_correct = typed_scores > threshold
    flat_correct = flat_scores > threshold

    # Discordant pairs
    b = int(np.sum(typed_correct & ~flat_correct))  # typed right, flat wrong
    c = int(np.sum(~typed_correct & flat_correct))  # typed wrong, flat right

    # Concordant (for reference)
    a = int(np.sum(typed_correct & flat_correct))
    d = int(np.sum(~typed_correct & ~flat_correct))

    # Exact binomial test: under H0, b/(b+c) ~ 0.5
    n_discordant = b + c
    if n_discordant == 0:
        p_value = 1.0
    else:
        result = binomtest(b, n_discordant, 0.5, alternative="two-sided")
        p_value = float(result.pvalue)

    return {
        "contingency": {"a": a, "b": b, "c": c, "d": d},
        "n_discordant": n_discordant,
        "p_value": p_value,
    }


def analyse_condition(
    typed_scores: np.ndarray,
    flat_scores: np.ndarray,
    label: str,
    rng: np.random.Generator,
) -> dict:
    """Full analysis for one category or overall."""
    delta = typed_scores - flat_scores
    typed_ci = bootstrap_ci(typed_scores, rng=rng)
    flat_ci = bootstrap_ci(flat_scores, rng=rng)
    delta_ci = bootstrap_ci(delta, rng=rng)
    mcnemar = mcnemar_exact(typed_scores, flat_scores)

    result = {
        "typed_mean": float(typed_scores.mean()),
        "typed_ci": list(typed_ci),
        "flat_mean": float(flat_scores.mean()),
        "flat_ci": list(flat_ci),
        "delta": float(delta.mean()),
        "delta_ci": list(delta_ci),
        "mcnemar_p": mcnemar["p_value"],
        "mcnemar_contingency": mcnemar["contingency"],
        "n_discordant": mcnemar["n_discordant"],
        "n": len(typed_scores),
    }

    logger.info(
        "  %s (n=%d): Δ=%+.3f, 95%% CI [%.3f, %.3f], McNemar p=%.4f (b=%d, c=%d)",
        label,
        len(typed_scores),
        result["delta"],
        delta_ci[0],
        delta_ci[1],
        mcnemar["p_value"],
        mcnemar["contingency"]["b"],
        mcnemar["contingency"]["c"],
    )
    return result


def run(trials_path: Path, output_path: Path) -> dict:
    """Run significance analysis on trial results."""
    trials = json.loads(trials_path.read_text())
    rng = np.random.default_rng(42)

    # Build paired arrays: match by question text, sorted consistently.
    questions = sorted({t["question"] for t in trials})
    typed_map = {t["question"]: t["score"] for t in trials if t["condition"] == "typed"}
    flat_map = {t["question"]: t["score"] for t in trials if t["condition"] == "flat"}
    cat_map = {t["question"]: t["category"] for t in trials}

    typed_all = np.array([typed_map[q] for q in questions])
    flat_all = np.array([flat_map[q] for q in questions])

    logger.info("=== Significance Analysis ===")

    results: dict = {}

    # Overall
    results["overall"] = analyse_condition(typed_all, flat_all, "overall", rng)

    # Per category
    for cat in ("contradiction_resolution", "temporal_reasoning"):
        mask = [cat_map[q] == cat for q in questions]
        typed_cat = typed_all[mask]
        flat_cat = flat_all[mask]
        results[cat] = analyse_condition(typed_cat, flat_cat, cat, rng)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2) + "\n")
    logger.info("Results saved to %s", output_path)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(Path("results/trials.json"), Path("results/significance.json"))

# Follow-up: Statistical Significance for BEAM Pilot

## Goal

Add error bars and a significance test to the BEAM pilot results (Table 4 in the paper). This closes the Experimental Rigor gap from 7.0→7.5, pushing the paper's review score from 7.475→7.55.

## What We Have

The pilot results are in `results/REPORT.md` and the raw trial data should be in `results/` (JSON or CSV with per-question scores for both conditions).

- **Typed condition**: 80 questions, mean score 0.463
- **Flat condition**: 80 questions, mean score 0.334
- **Per-question scores** are needed (not just aggregates)

## What We Need

1. **Bootstrap 95% confidence interval** on the per-condition means AND on the delta (typed - flat)
2. **McNemar test** (paired, since both conditions answer the same questions): are the conditions significantly different?
3. **Per-category breakdown**: CIs for contradiction-resolution and temporal-reasoning separately

## How to Do It

The raw per-question scores should be in the results directory. If they're in a JSON file from the experiment harness, load them. If only the report exists, check `src/evaluation/` for the scoring outputs.

### Bootstrap CI (primary)

```python
import numpy as np

def bootstrap_ci(scores: np.ndarray, n_boot: int = 10000, alpha: float = 0.05) -> tuple[float, float]:
    """Bootstrap percentile confidence interval."""
    rng = np.random.default_rng(42)
    boot_means = np.array([
        rng.choice(scores, size=len(scores), replace=True).mean()
        for _ in range(n_boot)
    ])
    lo = np.percentile(boot_means, 100 * alpha / 2)
    hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return lo, hi
```

Run on: typed_scores, flat_scores, and (typed_scores - flat_scores) for the paired delta CI.

### McNemar Test (secondary)

Convert scores to binary (>0.5 = correct, ≤0.5 = incorrect). Build the 2x2 contingency table:

|                     | Flat correct | Flat incorrect |
| ------------------- | ------------ | -------------- |
| **Typed correct**   | a            | b              |
| **Typed incorrect** | c            | d              |

McNemar tests whether b ≠ c (discordant pairs). Use `scipy.stats.contingency.mcnemar` or the exact binomial test if b+c < 25.

### What to Report

Add to the paper's pilot paragraph or table caption:

- Bootstrap 95% CI on the delta: e.g., "Δ = +0.128, 95% CI [0.03, 0.22]"
- McNemar p-value: e.g., "p = 0.02, McNemar exact test"
- Per-category CIs if sample is large enough

### Where to Put It

Update `~/dev/papers/03-missing-knowledge-layer/main.tex` in the pilot paragraph (§5). Change:

```
Typed routing improves overall accuracy by +0.128 (46.3\% vs.\ 33.4\%).
```

to something like:

```
Typed routing improves overall accuracy by +0.128 (46.3\% vs.\ 33.4\%,
bootstrap 95\% CI on $\Delta$: [X.XX, X.XX], McNemar $p = X.XX$).
```

## Output

Save results to `results/significance.json` with:

```json
{
  "overall": {"delta": 0.128, "ci_lo": ..., "ci_hi": ..., "mcnemar_p": ...},
  "contradiction": {"delta": 0.106, "ci_lo": ..., "ci_hi": ...},
  "temporal": {"delta": 0.150, "ci_lo": ..., "ci_hi": ...}
}
```

Then come back to the papers repo to update main.tex with the numbers.

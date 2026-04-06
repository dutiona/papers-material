# BEAM Typed-Routing Pilot — Full Experiment Runbook

You are running a controlled experiment for an academic paper. Follow this runbook exactly. Do not skip steps. Report every check result.

## Context

This experiment tests whether routing BEAM benchmark queries to typed memory stores (knowledge-base with supersession vs memory-engine with bi-temporal filtering) improves contradiction-resolution and temporal-reasoning scores compared to a flat baseline.

Results go into Section 5 of the paper at `~/dev/papers/03-missing-knowledge-layer/main.tex`.

## Phase 1: Environment Verification

Run ALL of these checks. If any fail, fix before proceeding.

### 1.1 Python environment

```bash
uv sync
PYTHONPATH=src uv run pytest -v
```

**Expected**: 57 tests pass. If any fail, diagnose and fix before continuing.

### 1.2 LM Studio (gemma4 — generation + scoring)

```bash
curl -s http://192.168.1.41:1234/v1/models | head -5
```

**Expected**: JSON response listing `google/gemma-4-26b-a4b`. If unreachable, ask the user to start LM Studio and load gemma4.

Test a chat call works:

```bash
PYTHONPATH=src uv run python -c "
from evaluation.llm import _chat
from config import Config
answer = _chat([{'role':'user','content':'Reply: SCORE: 3\nJUSTIFICATION: Test.'}], cfg=Config(), max_tokens=200)
print(f'Response: {repr(answer)}')
assert 'SCORE' in answer, 'Gemma4 not producing output — increase max_tokens or check model'
"
```

### 1.3 Ollama (embeddings)

```bash
OLLAMA_HOST=http://host.docker.internal:11434 uv run python -c "
from evaluation.embed import embed_single
from config import Config
emb = embed_single('test', cfg=Config())
print(f'Embedding dim: {len(emb)}')
assert len(emb) == 384, f'Expected 384-dim, got {len(emb)}'
"
```

**Expected**: `Embedding dim: 384`. If Ollama unreachable, ask user to start it. If model not found, run `ollama pull locusai/all-minilm-l6-v2`.

### 1.4 Memory-engine CLI

```bash
ME_CLI=~/dev/memory-engine/target/release/memory-engine-cli
test -x "$ME_CLI" && echo "ME CLI: OK" || echo "ME CLI: NOT BUILT — run: cd ~/dev/memory-engine && cargo build --release -p memory-engine-cli"
```

### 1.5 Knowledge-base library

```bash
PYTHONPATH=src uv run python -c "
from knowledge_base.db import get_connection, init_schema
from pathlib import Path
import tempfile
conn = get_connection(Path(tempfile.mktemp(suffix='.db')))
init_schema(conn)
print('KB library: OK')
"
```

## Phase 2: Clean State

Remove any previous experiment data:

```bash
rm -f data/kb.db data/kb.db-wal data/kb.db-shm
rm -f data/me.db data/me.db-wal data/me.db-shm
rm -f data/flat.db data/flat.db-wal data/flat.db-shm
rm -f results/summary.json results/trials.json
```

## Phase 3: Smoke Test

Run a 2-conversation smoke test to validate the pipeline end-to-end before committing to the full run (~9 min):

```bash
rm -f data/*.db data/*.db-*
PYTHONPATH=src OLLAMA_HOST=http://host.docker.internal:11434 \
  uv run python -m experiment --max-conversations 2 -v
```

**Verify**:

1. Ingestion completes for all 3 stores (KB chunks + conclusions, ME facts, flat chunks)
2. Non-zero scores appear for at least some trials
3. `results/summary.json` and `results/trials.json` are created
4. No `PARSE_ERROR` or `LLM_ERROR` in more than 20% of trials

```bash
PYTHONPATH=src uv run python -c "
import json
trials = json.loads(open('results/trials.json').read())
total = len(trials)
errors = sum(1 for t in trials if 'ERROR' in t['justification'])
nonzero = sum(1 for t in trials if t['score'] > 0)
print(f'Trials: {total}, Non-zero scores: {nonzero}, Parse errors: {errors}')
assert errors / total < 0.2, f'Too many parse errors: {errors}/{total}'
assert nonzero > 0, 'All scores are zero — retrieval or scoring is broken'
print('Smoke test: PASS')
"
```

If smoke test fails, diagnose and fix before proceeding.

## Phase 4: Full Experiment

Clean and run the full 20-conversation experiment (~90 min):

```bash
rm -f data/*.db data/*.db-*
rm -f results/summary.json results/trials.json
PYTHONPATH=src OLLAMA_HOST=http://host.docker.internal:11434 \
  uv run python -m experiment -v
```

**Expected output** (at the end):

```
============================================================
BEAM Typed-Routing Pilot — Results
============================================================
  contradiction_resolution    typed=X.XXX  flat=X.XXX  Δ=±X.XXX
  temporal_reasoning          typed=X.XXX  flat=X.XXX  Δ=±X.XXX
  OVERALL                     typed=X.XXX  flat=X.XXX  Δ=±X.XXX
============================================================
```

## Phase 5: Results Validation

### 5.1 Check for errors

```bash
PYTHONPATH=src uv run python -c "
import json
trials = json.loads(open('results/trials.json').read())
total = len(trials)
errors = sum(1 for t in trials if 'ERROR' in t['justification'])
print(f'Total trials: {total} (expected: 160)')
print(f'Parse/LLM errors: {errors} ({100*errors/total:.1f}%)')
for t in trials:
    if 'ERROR' in t['justification']:
        print(f'  [{t[\"condition\"]}] {t[\"category\"]}: {t[\"justification\"][:80]}')
"
```

### 5.2 Score distribution

```bash
PYTHONPATH=src uv run python -c "
import json
from collections import Counter
trials = json.loads(open('results/trials.json').read())
for cond in ('typed', 'flat'):
    scores = [t['score'] for t in trials if t['condition'] == cond]
    dist = Counter(scores)
    print(f'{cond}: mean={sum(scores)/len(scores):.3f} dist={dict(sorted(dist.items()))}')
"
```

### 5.3 Per-category breakdown

```bash
cat results/summary.json | python3 -m json.tool
```

### 5.4 Heuristic classifier accuracy (optional, run separately)

```bash
PYTHONPATH=src OLLAMA_HOST=http://host.docker.internal:11434 \
  uv run python -m experiment --max-conversations 2 --router heuristic -v
```

Compare oracle vs heuristic to measure routing error impact.

## Phase 6: Report Generation

Generate a LaTeX-ready results paragraph for the paper.

```bash
PYTHONPATH=src uv run python -c "
import json

summary = json.loads(open('results/summary.json').read())
trials = json.loads(open('results/trials.json').read())
total = len(trials)
n_per_condition = total // 2
cat_cond = summary['mean_by_category_and_condition']

cr = cat_cond['contradiction_resolution']
tr = cat_cond['temporal_reasoning']

print(r'''\paragraph{Pilot evaluation.}''')
print(f'To test whether architectural separation changes observable outcomes,')
print(f'we ran a focused pilot on {n_per_condition} BEAM probing questions')
print(f'({n_per_condition // 2} contradiction-resolution, {n_per_condition // 2} temporal-reasoning)')
print(f'from {len(set(t[\"conversation_id\"] for t in trials))} conversations in the 100K split.')
print(f'Each question was evaluated under two conditions: typed routing')
print(f'(contradiction \\\\to\\\\ knowledge-base, temporal \\\\to\\\\ memory-engine)')
print(f'and a flat baseline (undifferentiated SQLite+FTS5 store).')
print()
print(r'\\begin{table}[h]')
print(r'\\centering')
print(r'\\begin{tabular}{lccr}')
print(r'\\toprule')
print(r'Category & Typed & Flat & $\\Delta$ \\\\')
print(r'\\midrule')
print(f'Contradiction resolution & {cr[\"typed\"]:.3f} & {cr[\"flat\"]:.3f} & {cr[\"typed\"]-cr[\"flat\"]:+.3f} \\\\\\\\')
print(f'Temporal reasoning & {tr[\"typed\"]:.3f} & {tr[\"flat\"]:.3f} & {tr[\"typed\"]-tr[\"flat\"]:+.3f} \\\\\\\\')
overall = summary['mean_by_condition']
print(f'Overall & {overall[\"typed\"]:.3f} & {overall[\"flat\"]:.3f} & {overall[\"typed\"]-overall[\"flat\"]:+.3f} \\\\\\\\')
print(r'\\bottomrule')
print(r'\\end{tabular}')
print(r'\\caption{BEAM pilot: typed routing vs.\\\\ flat baseline on the two lowest-scoring categories.}')
print(r'\\label{tab:beam-pilot}')
print(r'\\end{table}')
"
```

Copy the output into `~/dev/papers/03-missing-knowledge-layer/main.tex` Section 5.

## Interpretation Guide

- **Positive Δ (typed > flat)**: Architectural separation measurably improves the specific abilities the paper identifies as broken. Even modest improvement (Δ > 0.05) supports the thesis.
- **Zero Δ**: Separation alone is insufficient without retrieval/reasoning changes. Still publishable — shows the gap requires more than architecture.
- **Negative Δ (typed < flat)**: Routing overhead or store-specific retrieval limitations hurt performance. Investigate per-trial justifications in `results/trials.json`.

## Limitations to acknowledge in the paper

1. Small sample: N=80 questions from 20 conversations (100K split only)
2. Two categories only (contradiction-resolution + temporal-reasoning)
3. No ablation (routing + store semantics tested jointly)
4. Heuristic contradiction detection during ingestion (not LLM-verified)
5. FTS-only retrieval (no vector search in KB or flat conditions)
6. Local model (gemma4 26b) for both generation and scoring

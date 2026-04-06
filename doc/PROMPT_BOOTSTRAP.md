# BEAM Typed-Routing Pilot Experiment

## Goal

Run a focused pilot experiment showing that routing BEAM queries to typed memory stores (knowledge-base vs memory-engine) based on query type improves contradiction-resolution and temporal-reasoning scores compared to a flat baseline. This is the single highest-leverage action to move paper #3 from Weak Accept (7.15) to solid Accept (7.6+).

## Context

Paper #3 ("The Missing Knowledge Layer in Cognitive Architectures for AI Agents") argues that conflating knowledge and memory produces category errors. BEAM (arXiv:2510.27246) benchmarks 10 memory abilities at up to 10M tokens. The two abilities where ALL systems score worst are:

- **Contradiction resolution**: <0.05 across all systems
- **Temporal reasoning**: 0.12 across all systems

These are precisely the abilities that require architectural solutions (supersession, bi-temporal modeling) rather than better retrieval. If typed routing improves these scores, it directly validates the thesis.

## Experiment Design

### Components

1. **BEAM subset**: 50-100 queries from the contradiction-resolution and temporal-reasoning categories. Download from the BEAM dataset (arXiv:2510.27246, check for public dataset release or reconstruct from the paper's examples).

2. **Query classifier**: A simple router that classifies each BEAM query as:
   - `knowledge` → route to knowledge-base (supersession-aware retrieval)
   - `memory` → route to memory-engine (temporal/episodic retrieval)
   - `mixed` → route to both, merge results

3. **Typed routing condition**: Queries hit KB or ME based on classification. KB handles contradiction-resolution (supersession semantics). ME handles temporal-reasoning (bi-temporal model).

4. **Flat baseline**: Same queries hit a single undifferentiated SQLite+vec store with identical retrieval (FTS5+vector+RRF) but no type distinction, no supersession, no bi-temporal timestamps.

5. **Evaluation**: Per-category accuracy on contradiction-resolution and temporal-reasoning. Report N, per-category scores, classifier accuracy, and flat baseline scores.

### Companion Systems

- **knowledge-base**: `~/dev/knowledge-base/` — Python MCP server, 46 tools, hybrid search (FTS5 + vector + RRF), stage-2 reranking, entity resolution, 338+ tests. Supersession-aware: old claims linked to successors, never deleted.
- **memory-engine**: `~/dev/memory-engine/` — Rust crate, 5 primitives, bi-temporal (4 timestamps per fact), Ebbinghaus forgetting, 486 tests. Consumer traits for embedding/summary/conflict/persistence/reranking.

### What a Positive Result Looks Like

Even a modest improvement is sufficient:

- Contradiction-resolution: 0.05 → 0.15 with typed routing
- Temporal-reasoning: 0.12 → 0.20 with typed routing

The claim isn't SOTA. The claim is that architectural separation measurably improves the specific abilities the paper identifies as broken.

### What to Report

Add results as a new paragraph or small table in §5 (Companion Implementations) of the paper at `~/dev/papers/03-missing-knowledge-layer/main.tex`. Format:

```latex
\paragraph{Pilot evaluation.}
In order to test whether the architectural separation changes observable
outcomes, we ran a focused pilot on N BEAM queries...
```

### Design Notes (from the paper review)

1. Report per-category scores separately (contradiction-resolution and temporal-reasoning)
2. Include the flat baseline to isolate typed routing from retrieval quality
3. Report classifier accuracy — if the router misclassifies, separate routing errors from architecture effects
4. State the N (50-100) and acknowledge limitations (small sample, two categories only, no ablation)
5. A negative result is also publishable — shows separation alone is insufficient without retrieval/reasoning changes

### Repo Structure

```
beam-pilot/
├── README.md
├── pyproject.toml          # uv project, Python 3.12+
├── src/
│   ├── dataset/            # BEAM subset loading/caching
│   ├── classifier/         # Query type classifier
│   ├── routing/            # Typed routing to KB/ME
│   ├── baseline/           # Flat store baseline
│   └── evaluation/         # Scoring + reporting
├── data/                   # BEAM subset (gitignored if large)
├── results/                # Output scores, tables
└── tests/
```

### Tech Stack

- Python 3.12+, uv
- knowledge-base accessed via its MCP tools or direct SQLite
- memory-engine accessed via its MCP server or direct Rust FFI (if Python bindings exist) or via subprocess
- ruff for formatting/linting, pyright for types, pytest for tests

### Time Budget

2-3 hours total:

- 30min: repo setup + BEAM dataset acquisition
- 30min: query classifier
- 30min: typed routing harness
- 30min: flat baseline
- 30min: evaluation + reporting
- 30min: integrate results into paper

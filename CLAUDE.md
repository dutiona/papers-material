# BEAM Typed-Routing Pilot Experiment

## What

Academic experiment repo testing whether typed memory routing improves BEAM benchmark scores on contradiction-resolution and temporal-reasoning. Companion to the position paper "The Missing Knowledge Layer in Cognitive Architectures for AI Agents."

Three stores, same data, different semantics:

- **KB** (`knowledge-base` at `~/dev/knowledge-base/`): supersession-aware conclusions
- **ME** (`memory-engine` at `~/dev/memory-engine/`): bi-temporal facts via CLI
- **Flat**: SQLite+FTS5 control with no type semantics

## How

```bash
uv sync                                               # install deps
PYTHONPATH=src uv run pytest -v                        # 57 tests, all must pass
PYTHONPATH=src uv run python -m experiment -v          # full run (~90 min)
PYTHONPATH=src uv run python -m experiment --max-conversations 2 -v  # smoke test
```

Environment variables required:

- `PYTHONPATH=src` (always)
- `OLLAMA_HOST=http://host.docker.internal:11434` (WSL → Windows Ollama)

## Infrastructure

| Service   | Host                                                   | Model                      | Use                                                          |
| --------- | ------------------------------------------------------ | -------------------------- | ------------------------------------------------------------ |
| LM Studio | `192.168.1.41:1234`                                    | `google/gemma-4-26b-a4b`   | Chat (generation + scoring)                                  |
| Ollama    | `host.docker.internal:11434`                           | `locusai/all-minilm-l6-v2` | Embeddings (384-dim)                                         |
| ME CLI    | `~/dev/memory-engine/target/release/memory-engine-cli` | —                          | Must be built (`cargo build --release -p memory-engine-cli`) |

## Code conventions

- Python 3.12+, `uv` (never pip), `ruff` format+lint, `pyright` strict, `pytest`
- `src/` layout with `PYTHONPATH=src`
- FTS5 queries must be sanitized (use `_to_search_keywords()` from `routing/router.py`)
- ME CLI has a read-only limitation: use accumulate+flush pattern, not per-conversation writes

## Key design decisions

Read `doc/debate-scoring-prompt/` for the 3-round multi-model debate that produced the scoring prompt. Read `doc/PROMPT.md` for the full experiment design specification.

- **Option C ingestion**: all turns into all stores; store semantics are the independent variable
- **Oracle routing**: uses BEAM ground-truth labels (isolates architecture effect from routing error)
- **Scoring**: 0-4 integer scale, explicit category param, hard caps (side-picking ≤0, wrong temporal ≤2)
- **Gemma4 reasoning**: needs max_tokens=1024+ (reasoning consumes ~700 tokens before output)

## Do not

- Do not use pip; use uv
- Do not access ME via direct SQL; use the CLI wrapper in `routing/me_store.py`
- Do not pass raw natural-language questions to FTS5; always sanitize first
- Do not edit `~/dev/knowledge-base/` or `~/dev/memory-engine/` from this repo

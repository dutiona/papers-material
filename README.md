# BEAM Typed-Routing Pilot Experiment

Pilot experiment for the position paper _"The Missing Knowledge Layer in Cognitive Architectures for AI Agents"_. Tests whether routing BEAM benchmark queries to typed memory stores (knowledge-base with supersession vs memory-engine with bi-temporal) improves contradiction-resolution and temporal-reasoning scores compared to a flat baseline.

## Thesis

AI memory systems conflate knowledge with memory, producing a category error: applying cognitive decay to facts. The four-layer decomposition (Knowledge/Memory/Wisdom/Intelligence) assigns distinct persistence semantics to each cognitive substrate. This experiment validates the architecture by measuring whether typed routing improves the two BEAM categories where all systems score worst.

## Architecture

```
BEAM dataset (HuggingFace Mohammadta/BEAM, 100K split)
  │
  ├── 20 conversations, 5732 turns, 80 experiment questions
  │   (40 contradiction-resolution + 40 temporal-reasoning)
  │
  ▼ Ingestion (Option C: all turns into all stores)
  ┌──────────────┬──────────────┬──────────────┐
  │  KB Store    │  ME Store    │  Flat Store  │
  │  (knowledge- │  (memory-    │  (SQLite +   │
  │   base)      │   engine)    │   FTS5)      │
  │              │              │              │
  │ Supersession │ Bi-temporal  │ No type      │
  │ chains for   │ filtering    │ semantics    │
  │ contradictions│ for temporal │ (control)    │
  └──────┬───────┴──────┬───────┴──────┬───────┘
         │              │              │
         ▼              ▼              ▼
  Query Classifier (oracle / heuristic)
         │
         ├── contradiction → KB (supersession-filtered retrieval)
         ├── temporal → ME (bi-temporal retrieval)
         └── flat baseline → FlatStore (FTS only)
         │
         ▼
  LLM Generation (gemma4 26b via LM Studio)
         │
         ▼
  LLM Scoring (debate-designed prompt, 0-4 integer scale)
         │
         ▼
  results/summary.json + results/trials.json
```

## Quick start

```bash
# Prerequisites: uv, Ollama (embeddings), LM Studio (gemma4)
uv sync
PYTHONPATH=src OLLAMA_HOST=http://host.docker.internal:11434 \
  uv run pytest -v                                    # 57 tests

# Smoke test (2 conversations, ~9 min)
PYTHONPATH=src OLLAMA_HOST=http://host.docker.internal:11434 \
  uv run python -m experiment --max-conversations 2 -v

# Full experiment (20 conversations, ~90 min)
PYTHONPATH=src OLLAMA_HOST=http://host.docker.internal:11434 \
  uv run python -m experiment -v
```

## Project structure

```
src/
├── config.py               # Central config (LLM providers, DB paths)
├── experiment.py            # Main experiment runner + CLI
├── dataset/                 # BEAM dataset loading and types
│   ├── types.py             # ChatTurn, ProbingQuestion, Conversation
│   └── loader.py            # HuggingFace loader + parser
├── baseline/
│   └── store.py             # Flat SQLite+FTS5 store (control condition)
├── classifier/
│   └── router.py            # Oracle + heuristic query classification
├── evaluation/
│   ├── llm.py               # LLM generation + scoring (debate-designed prompt)
│   ├── embed.py             # Ollama embedding interface
│   └── types.py             # TrialResult, ExperimentReport
└── routing/
    ├── kb_store.py           # knowledge-base wrapper (supersession)
    ├── me_store.py           # memory-engine wrapper (bi-temporal via CLI)
    ├── ingest.py             # BEAM → KB/ME/flat ingestion pipeline
    └── router.py             # Typed routing dispatch
tests/                       # 57 tests across all modules
doc/
├── PROMPT.md                # Experiment design specification
└── debate-scoring-prompt/   # 3-round scoring prompt debate record
```

## External dependencies

| System                                  | Location                     | Role                                              |
| --------------------------------------- | ---------------------------- | ------------------------------------------------- |
| [knowledge-base](../../knowledge-base/) | `~/dev/knowledge-base/`      | Python MCP server, supersession-aware conclusions |
| [memory-engine](../../memory-engine/)   | `~/dev/memory-engine/`       | Rust crate, bi-temporal facts via CLI             |
| Ollama                                  | `host.docker.internal:11434` | `all-minilm-l6-v2` embeddings (384-dim)           |
| LM Studio                               | `192.168.1.41:1234`          | `gemma-4-26b-a4b` for generation + scoring        |

## Paper

Results feed into Section 5 (Companion Implementations) of `~/dev/papers/03-missing-knowledge-layer/main.tex`.

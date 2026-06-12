"""Experiment configuration: LLM providers, model names, paths.

Endpoint fields read environment variables first (CHAT_BASE_URL,
CHAT_MODEL, OLLAMA_HOST) so runs can target whatever host serves the
models without editing this file; the historical defaults remain the
fallbacks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Config:
    """Central configuration for the BEAM pilot experiment."""

    # --- LM Studio (gemma4, OpenAI-compatible) ---
    chat_base_url: str = field(
        default_factory=lambda: os.environ.get("CHAT_BASE_URL", "http://192.168.1.41:1234/v1")
    )
    chat_model: str = field(
        default_factory=lambda: os.environ.get("CHAT_MODEL", "google/gemma-4-26b-a4b")
    )
    chat_max_tokens: int = 1024
    chat_temperature: float = 0.0

    # --- Ollama (embeddings) ---
    ollama_host: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434")
    )
    embed_model: str = "locusai/all-minilm-l6-v2:latest"
    embed_dim: int = 384

    # --- Local database paths (experiment-local, not production) ---
    data_dir: Path = field(default_factory=lambda: Path("data"))

    @property
    def kb_db_path(self) -> Path:
        return self.data_dir / "kb.db"

    @property
    def me_db_path(self) -> Path:
        return self.data_dir / "me.db"

    @property
    def flat_db_path(self) -> Path:
        return self.data_dir / "flat.db"

    @property
    def results_dir(self) -> Path:
        return Path("results")

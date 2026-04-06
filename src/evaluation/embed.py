"""Embedding interface via Ollama."""

from __future__ import annotations

import logging
import os

import ollama

from config import Config

logger = logging.getLogger(__name__)

_DEFAULT_CFG = Config()


def embed(texts: list[str], *, cfg: Config | None = None) -> list[list[float]]:
    """Embed a batch of texts via Ollama.

    Args:
        texts: List of strings to embed.
        cfg: Experiment config (for host + model).

    Returns:
        List of embedding vectors, one per input text.
    """
    c = cfg or _DEFAULT_CFG

    # Ollama client reads OLLAMA_HOST env var.
    old_host = os.environ.get("OLLAMA_HOST")
    os.environ["OLLAMA_HOST"] = c.ollama_host
    try:
        result = ollama.embed(model=c.embed_model, input=texts)  # pyright: ignore[reportUnknownMemberType]
        return [list(e) for e in result.embeddings]  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    finally:
        if old_host is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = old_host


def embed_single(text: str, *, cfg: Config | None = None) -> list[float]:
    """Embed a single text string."""
    return embed([text], cfg=cfg)[0]

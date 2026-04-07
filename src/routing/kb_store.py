"""Knowledge-base store wrapper: supersession-aware ingestion and retrieval.

Wraps the knowledge-base library for the BEAM pilot experiment.
Ingests conversation turns as chunks (for FTS) and factual claims as
conclusions (for supersession tracking).
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

from knowledge_base.conclusions import (
    get_conclusions,
    record_conclusion,
    supersede_conclusion,
)
from knowledge_base.db import get_connection, init_schema
from knowledge_base.search import search as kb_search

from config import Config
from dataset.types import ChatTurn

logger = logging.getLogger(__name__)


class KBStore:
    """Knowledge-base store with supersession-aware conclusions."""

    def __init__(self, db_path: Path, *, cfg: Config | None = None) -> None:
        self._cfg = cfg or Config()
        self._conn = get_connection(db_path)
        init_schema(self._conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> KBStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Ingestion ──────────────────────────────────────────────────

    def ingest_turn(self, turn: ChatTurn, conversation_id: str) -> int:
        """Insert a conversation turn as a searchable chunk.

        Uses direct SQL insert (bypasses KB's ingest pipeline which requires
        embeddings). FTS triggers populate the full-text index automatically.

        Returns the chunk ID.
        """
        content_hash = hashlib.sha256(turn.content.encode()).hexdigest()
        cursor = self._conn.execute(
            """\
            INSERT OR IGNORE INTO chunks (content_hash, content, source_type, source_uri, chunk_index, chunk_strategy)
            VALUES (?, ?, 'note', ?, ?, 'mechanical')""",
            (content_hash, turn.content, f"beam://{conversation_id}", turn.turn_id),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def ingest_turns_batch(self, turns: list[ChatTurn], conversation_id: str) -> int:
        """Bulk-insert conversation turns as chunks. Returns count inserted."""
        rows = [
            (
                hashlib.sha256(t.content.encode()).hexdigest(),
                t.content,
                f"beam://{conversation_id}",
                t.turn_id,
            )
            for t in turns
        ]
        self._conn.executemany(
            """\
            INSERT OR IGNORE INTO chunks (content_hash, content, source_type, source_uri, chunk_index, chunk_strategy)
            VALUES (?, ?, 'note', ?, ?, 'mechanical')""",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def record_claim(
        self,
        claim: str,
        *,
        confidence: float = 1.0,
        source_chunk_ids: list[int] | None = None,
        context: str = "",
    ) -> int:
        """Record a factual claim as a conclusion. Returns the conclusion ID."""
        result = record_conclusion(
            self._conn,
            claim,
            confidence=confidence,
            source_chunk_ids=source_chunk_ids,
            session_context=context,
        )
        return int(result["conclusion_id"])

    def supersede_claim(
        self,
        old_id: int,
        new_claim: str,
        *,
        confidence: float = 1.0,
        source_chunk_ids: list[int] | None = None,
        context: str = "",
    ) -> int:
        """Supersede an existing claim with a new one. Returns new conclusion ID."""
        result = supersede_conclusion(
            self._conn,
            old_id,
            new_claim,
            confidence=confidence,
            source_chunk_ids=source_chunk_ids,
            session_context=context,
        )
        return int(result["new_conclusion_id"])

    # ── Retrieval ──────────────────────────────────────────────────

    def search(self, query: str, *, top_k: int = 10) -> list[dict[str, object]]:
        """FTS search over ingested chunks. Returns list of {content, score}."""
        results = kb_search(self._conn, query, top_k=top_k, mode="fts")
        return [{"content": r.content, "score": r.score, "chunk_id": r.chunk_id} for r in results]

    def get_active_conclusions(self, keyword: str | None = None) -> list[dict[str, object]]:
        """Get active (non-superseded) conclusions, optionally filtered by keyword."""
        return [dict(c) for c in get_conclusions(self._conn, keyword=keyword)]

    def get_all_conclusions(self, keyword: str | None = None) -> list[dict[str, object]]:
        """Get all conclusions including superseded ones."""
        return [
            dict(c) for c in get_conclusions(self._conn, keyword=keyword, include_superseded=True)
        ]

    def retrieve_with_supersession(self, query: str, *, top_k: int = 10) -> str:
        """Retrieve context for a query, enriched with supersession awareness.

        Combines FTS search results with active conclusions.
        For contradiction-resolution queries, this is the key differentiator:
        superseded claims are excluded, only the latest version surfaces.
        """
        # FTS search for relevant chunks.
        chunks = self.search(query, top_k=top_k)

        # Also check conclusions (supersession-filtered).
        conclusions = self.get_active_conclusions()

        # Build context string.
        parts: list[str] = []
        if chunks:
            parts.append("=== Retrieved conversation excerpts ===")
            for c in chunks:
                parts.append(str(c["content"]))
        if conclusions:
            parts.append("\n=== Active factual conclusions (supersession-filtered) ===")
            for c in conclusions:
                parts.append(f"- {c['claim']} (confidence: {c.get('confidence', '?')})")

        return "\n\n".join(parts) if parts else "(no relevant context found)"

    # ── Stats ──────────────────────────────────────────────────────

    def chunk_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return int(row[0]) if row else 0

    def conclusion_count(self, *, include_superseded: bool = False) -> int:
        if include_superseded:
            row = self._conn.execute("SELECT COUNT(*) FROM conclusions").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM conclusions WHERE superseded_by IS NULL"
            ).fetchone()
        return int(row[0]) if row else 0

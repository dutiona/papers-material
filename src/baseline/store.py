"""Flat baseline store: SQLite + FTS5 without supersession or bi-temporal semantics.

This is the control condition. Same retrieval algorithm (FTS5 + BM25),
same data, but no architectural awareness of contradiction or temporal validity.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single retrieval result from the flat store."""

    fact_id: int
    content: str
    score: float
    created_at: str
    metadata_json: str


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    time_anchor TEXT,          -- raw time anchor from BEAM (stored but NOT used for filtering)
    conversation_id TEXT,
    turn_id INTEGER,
    role TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    content,
    content='facts',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Keep FTS index in sync.
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO facts_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


class FlatStore:
    """Flat SQLite store with FTS5 search. No supersession, no bi-temporal filtering."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> FlatStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def ingest(
        self,
        content: str,
        *,
        conversation_id: str = "",
        turn_id: int = -1,
        role: str = "",
        time_anchor: str = "",
        metadata: str = "{}",
    ) -> int:
        """Insert a single fact. Returns the fact ID."""
        cursor = self._conn.execute(
            """\
            INSERT INTO facts (content, conversation_id, turn_id, role, time_anchor, metadata)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (content, conversation_id, turn_id, role, time_anchor, metadata),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def ingest_batch(
        self,
        rows: list[tuple[str, str, int, str, str, str]],
    ) -> int:
        """Bulk insert facts. Each tuple: (content, conv_id, turn_id, role, time_anchor, metadata).

        Returns the number of rows inserted.
        """
        self._conn.executemany(
            """\
            INSERT INTO facts (content, conversation_id, turn_id, role, time_anchor, metadata)
            VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def search(self, query: str, *, top_k: int = 10) -> list[SearchResult]:
        """FTS5 search with BM25 ranking. No temporal filtering."""
        # Sanitize query: strip FTS5 special chars that cause syntax errors.
        sanitized = _sanitize_fts5_query(query)
        if not sanitized.strip():
            return []
        rows = self._conn.execute(
            """\
            SELECT f.id, f.content, fts.rank, f.created_at, f.metadata
            FROM facts_fts fts
            JOIN facts f ON f.id = fts.rowid
            WHERE facts_fts MATCH ?
            ORDER BY fts.rank
            LIMIT ?""",
            (sanitized, top_k),
        ).fetchall()
        return [
            SearchResult(
                fact_id=r[0],
                content=r[1],
                score=-r[2],  # FTS5 rank is negative (lower = better), flip for clarity
                created_at=r[3],
                metadata_json=r[4],
            )
            for r in rows
        ]

    def count(self) -> int:
        """Total number of facts in the store."""
        row = self._conn.execute("SELECT COUNT(*) FROM facts").fetchone()
        return int(row[0]) if row else 0


def _sanitize_fts5_query(query: str) -> str:
    """Strip FTS5 special characters that cause syntax errors.

    FTS5 treats ?, *, ^, :, (, ), {, }, [, ], +, - as operators.
    We keep only alphanumeric words joined by spaces (implicit OR).
    """
    words = re.findall(r"\b\w+\b", query)
    return " ".join(words)

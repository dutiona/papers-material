"""Memory-engine store wrapper: bi-temporal ingestion and retrieval via CLI.

Wraps the memory-engine CLI (batch-ingest, query --valid-at) for the BEAM
pilot experiment. All interaction is via subprocess — no Rust FFI.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from config import Config
from dataset.types import ChatTurn

logger = logging.getLogger(__name__)

_ME_CLI = Path.home() / "dev/memory-engine/target/release/memory-engine-cli"


class MEStore:
    """Memory-engine store with bi-temporal querying via CLI.

    Due to a ME CLI limitation (existing DBs open read-only for batch-ingest),
    all ingestion must happen in a single batch-ingest --create call.
    Use prepare_turns() to accumulate, then flush() to write all at once.
    """

    def __init__(self, db_path: Path, *, cfg: Config | None = None) -> None:
        self._cfg = cfg or Config()
        self._db_path = db_path
        self._pending_lines: list[str] = []
        self._flushed = False

    @property
    def db_path(self) -> Path:
        return self._db_path

    # ── Ingestion ──────────────────────────────────────────────────

    def ingest_turns(self, turns: list[ChatTurn], conversation_id: str) -> int:
        """Accumulate conversation turns for later batch-ingest.

        Call flush() after all conversations are prepared to write everything
        in a single CLI call.
        """
        count = 0
        for turn in turns:
            fact: dict[str, object] = {
                "content": turn.content[:2000],
                "fact_type": "episodic" if turn.role == "user" else "semantic",
                "importance": 0.7 if turn.role == "user" else 0.4,
                "metadata": {
                    "conversation_id": conversation_id,
                    "turn_id": turn.turn_id,
                    "role": turn.role,
                },
            }
            t_valid = _parse_time_anchor(turn.time_anchor)
            if t_valid:
                fact["t_valid"] = t_valid
            self._pending_lines.append(json.dumps(fact))
            count += 1
        return count

    def flush(self) -> int:
        """Write all accumulated facts to ME via a single batch-ingest --create call.

        Returns the number of facts ingested.
        """
        if not self._pending_lines:
            return 0
        if self._flushed:
            logger.warning("ME flush() called twice — ignoring (ME CLI read-only limitation)")
            return 0

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(self._pending_lines))
            jsonl_path = f.name

        try:
            cmd = [
                str(_ME_CLI),
                "--db",
                str(self._db_path),
                "batch-ingest",
                "--file",
                jsonl_path,
                "--embed-url",
                f"{self._cfg.ollama_host}/v1/embeddings",
                "--embed-model",
                self._cfg.embed_model,
                "--create",
                "--embed-dim",
                str(self._cfg.embed_dim),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                logger.error("ME batch-ingest failed: %s", result.stderr)
                return 0

            logger.info("ME flush: %s", result.stdout.strip())
            self._flushed = True
            count = len(self._pending_lines)
            self._pending_lines.clear()
            return count
        finally:
            Path(jsonl_path).unlink(missing_ok=True)

    # ── Retrieval ──────────────────────────────────────────────────

    def query(
        self,
        text: str,
        *,
        top_k: int = 10,
        valid_at: str | None = None,
        fact_type: str | None = None,
    ) -> list[dict[str, object]]:
        """Query ME via CLI with optional temporal filtering.

        Args:
            text: Search text (FTS5).
            top_k: Max results.
            valid_at: RFC 3339 timestamp for bi-temporal filtering.
            fact_type: Filter by episodic/semantic/procedural.

        Returns:
            List of fact dicts with content, score, temporal fields.
        """
        cmd = [
            str(_ME_CLI),
            "--db",
            str(self._db_path),
            "--format",
            "json",
            "query",
            text,
            "--limit",
            str(top_k),
        ]
        if valid_at:
            cmd.extend(["--valid-at", valid_at])
        if fact_type:
            cmd.extend(["--fact-type", fact_type])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error("ME query failed: %s", result.stderr)
            return []

        try:
            raw: list[dict[str, object]] = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error("ME query returned invalid JSON: %s", result.stdout[:200])
            return []

        # Extract just what we need (skip the huge embedding vectors).
        return [
            {
                "content": _nested_get(item, "fact", "content", default=""),
                "score": item.get("score", 0.0),
                "fact_type": _nested_get(item, "fact", "fact_type", default=""),
                "t_valid": _nested_get(item, "fact", "t_valid"),
                "t_invalid": _nested_get(item, "fact", "t_invalid"),
                "importance": _nested_get(item, "fact", "importance", default=0.0),
            }
            for item in raw
        ]

    def retrieve_temporal(self, query: str, *, valid_at: str | None = None, top_k: int = 10) -> str:
        """Retrieve context for a temporal reasoning query.

        The key differentiator: bi-temporal filtering ensures only facts
        valid at the queried time point are returned.
        """
        results = self.query(query, top_k=top_k, valid_at=valid_at)

        if not results:
            return "(no relevant context found)"

        parts = ["=== Retrieved facts (bi-temporal filtered) ==="]
        for r in results:
            validity = ""
            if r.get("t_valid"):
                validity = f" [valid from: {r['t_valid']}"
                if r.get("t_invalid"):
                    validity += f" to: {r['t_invalid']}"
                validity += "]"
            parts.append(f"- {r['content']}{validity}")

        return "\n".join(parts)

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> str:
        """Get ME database stats."""
        result = subprocess.run(
            [str(_ME_CLI), "--db", str(self._db_path), "stats"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout if result.returncode == 0 else result.stderr


# ── Helpers ────────────────────────────────────────────────────────

_MONTH_MAP: dict[str, str] = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def _parse_time_anchor(anchor: str) -> str | None:
    """Parse BEAM time_anchor (e.g., 'March-15') into RFC 3339.

    Returns None if unparseable. Assumes year 2024 (BEAM conversations
    are set in 2024).
    """
    if not anchor or not anchor.strip():
        return None

    import re

    # Format: "Month-Day" or "Month Day"
    m = re.match(r"(\w+)[-\s]+(\d{1,2})", anchor.strip())
    if not m:
        return None

    month_str = m.group(1).lower()
    day = int(m.group(2))

    month = _MONTH_MAP.get(month_str)
    if not month:
        return None

    return f"2024-{month}-{day:02d}T00:00:00Z"


def _nested_get(d: dict[str, object], *keys: str, default: object = None) -> object:
    """Safely get a nested dict value."""
    current: object = d
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current

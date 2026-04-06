"""Tests for the ME store wrapper (requires ME CLI built + Ollama running)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from config import Config
from dataset.types import ChatTurn
from routing.me_store import MEStore, _parse_time_anchor

# Skip all tests if ME CLI is not built or Ollama is unreachable.
_ME_CLI = Path.home() / "dev/memory-engine/target/release/memory-engine-cli"
_requires_me_cli = pytest.mark.skipif(not _ME_CLI.exists(), reason="ME CLI not built")


class TestParseTimeAnchor:
    """Unit tests — no external deps."""

    def test_standard_format(self) -> None:
        assert _parse_time_anchor("March-15") == "2024-03-15T00:00:00Z"

    def test_with_space(self) -> None:
        assert _parse_time_anchor("January 1") == "2024-01-01T00:00:00Z"

    def test_abbreviated_month(self) -> None:
        assert _parse_time_anchor("Feb-28") == "2024-02-28T00:00:00Z"

    def test_empty(self) -> None:
        assert _parse_time_anchor("") is None

    def test_garbage(self) -> None:
        assert _parse_time_anchor("hello world") is None


@_requires_me_cli
class TestMEStoreIntegration:
    """Integration tests — require ME CLI + Ollama."""

    @pytest.fixture()
    def me_store(self, tmp_path: Path) -> MEStore:
        db_path = tmp_path / "test-me.db"
        cfg = Config()
        return MEStore(db_path, cfg=cfg)

    def test_ingest_and_query(self, me_store: MEStore) -> None:
        turns = [
            ChatTurn("User moved to Istanbul in March", 1, "1,1", "q", "user", "March-1"),
            ChatTurn("Property viewing on March 25", 2, "1,2", "q", "user", "March-25"),
            ChatTurn("Property viewing on March 27", 3, "1,3", "q", "user", "March-27"),
        ]
        count = me_store.ingest_turns(turns, "conv-test")
        assert count == 3
        me_store.flush()

        results = me_store.query("property viewing")
        assert len(results) >= 1
        assert any("property" in str(r["content"]).lower() for r in results)

    def test_temporal_filtering(self, me_store: MEStore) -> None:
        turns = [
            ChatTurn("Meeting scheduled for project kickoff", 1, "1,1", "q", "user", "March-10"),
            ChatTurn("Meeting for midpoint review of project", 2, "1,2", "q", "user", "March-20"),
            ChatTurn("Meeting for final review of project", 3, "1,3", "q", "user", "March-30"),
        ]
        me_store.ingest_turns(turns, "conv-test")
        me_store.flush()

        all_results = me_store.query("meeting project")
        assert len(all_results) == 3

        filtered = me_store.query("meeting project", valid_at="2024-03-15T00:00:00Z")
        contents = [str(r["content"]) for r in filtered]
        assert len(filtered) == 1, f"Expected 1 result, got {len(filtered)}: {contents}"
        assert "kickoff" in contents[0]

    def test_retrieve_temporal_context(self, me_store: MEStore) -> None:
        turns = [
            ChatTurn("Started Flask project on March 1", 1, "1,1", "q", "user", "March-1"),
            ChatTurn("Completed user auth on March 15", 2, "1,2", "q", "user", "March-15"),
        ]
        me_store.ingest_turns(turns, "conv-test")
        me_store.flush()

        context = me_store.retrieve_temporal("Flask project", valid_at="2024-03-10T00:00:00Z")
        assert "Flask" in context
        assert "bi-temporal" in context.lower() or "Retrieved" in context

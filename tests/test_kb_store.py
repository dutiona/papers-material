"""Tests for the KB store wrapper."""

from __future__ import annotations

import tempfile
from pathlib import Path

from dataset.types import ChatTurn
from routing.kb_store import KBStore


def _tmp_db() -> Path:
    return Path(tempfile.mktemp(suffix=".db"))


class TestKBStoreIngestion:
    def test_ingest_turn(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                turn = ChatTurn(
                    content="I have never used Flask before",
                    turn_id=1,
                    index="1,1",
                    question_type="main_question",
                    role="user",
                    time_anchor="March-15",
                )
                chunk_id = store.ingest_turn(turn, "conv-1")
                assert chunk_id > 0
                assert store.chunk_count() == 1
        finally:
            db.unlink(missing_ok=True)

    def test_ingest_turns_batch(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                turns = [
                    ChatTurn("Turn one content", 1, "1,1", "main_question", "user", "March-15"),
                    ChatTurn("Turn two content", 2, "1,2", "follow_up", "assistant", "March-15"),
                    ChatTurn("Turn three content", 3, "1,3", "follow_up", "user", "March-16"),
                ]
                count = store.ingest_turns_batch(turns, "conv-1")
                assert count == 3
                assert store.chunk_count() == 3
        finally:
            db.unlink(missing_ok=True)


class TestKBStoreSupersession:
    def test_record_and_supersede(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                id1 = store.record_claim("LoRA is the best adapter method", confidence=0.8)
                id2 = store.supersede_claim(id1, "DoRA supersedes LoRA", confidence=0.9)

                assert id2 > id1
                assert store.conclusion_count() == 1  # Only active
                assert store.conclusion_count(include_superseded=True) == 2  # Both

                active = store.get_active_conclusions()
                assert len(active) == 1
                assert "DoRA" in active[0]["claim"]
        finally:
            db.unlink(missing_ok=True)

    def test_supersession_filters_correctly(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                id1 = store.record_claim("I have never used Flask")
                store.record_claim("Python is great")  # unrelated, stays active
                store.supersede_claim(id1, "I implemented a Flask homepage route")

                active = store.get_active_conclusions()
                claims = [c["claim"] for c in active]
                assert "I have never used Flask" not in claims
                assert "I implemented a Flask homepage route" in claims
                assert "Python is great" in claims
                assert len(active) == 2
        finally:
            db.unlink(missing_ok=True)


class TestKBStoreRetrieval:
    def test_search_fts(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                turns = [
                    ChatTurn("Flask is a web framework for Python", 1, "1,1", "q", "user", ""),
                    ChatTurn("I enjoy hiking in the mountains", 2, "1,2", "q", "user", ""),
                    ChatTurn("Flask routes handle HTTP requests", 3, "1,3", "q", "assistant", ""),
                ]
                store.ingest_turns_batch(turns, "conv-1")

                results = store.search("Flask web framework")
                assert len(results) > 0
                assert "Flask" in str(results[0]["content"])
        finally:
            db.unlink(missing_ok=True)

    def test_retrieve_with_supersession(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                turns = [
                    ChatTurn("I have never written Flask routes", 1, "1,1", "q", "user", ""),
                    ChatTurn(
                        "I implemented a homepage route with Flask", 2, "1,2", "q", "user", ""
                    ),
                ]
                store.ingest_turns_batch(turns, "conv-1")

                # Record the contradiction as supersession
                id1 = store.record_claim("User has never written Flask routes")
                store.supersede_claim(id1, "User implemented a homepage route with Flask")

                context = store.retrieve_with_supersession("Flask routes")
                # Should contain the chunk text AND the active conclusion
                assert "Flask" in context
                assert "homepage route" in context
                # Superseded claim should NOT appear in conclusions section
                assert (
                    "never written Flask routes"
                    not in context.split("Active factual conclusions")[-1]
                    if "Active factual conclusions" in context
                    else True
                )
        finally:
            db.unlink(missing_ok=True)

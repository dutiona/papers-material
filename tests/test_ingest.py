"""Tests for the ingestion pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

from baseline.store import FlatStore
from dataset.types import ChatTurn, Conversation, QuestionCategory
from routing.ingest import (
    _extract_claim,
    _has_negation_overlap,
    _is_factual_claim,
    ingest_conversation_flat,
    ingest_conversation_kb,
)
from routing.kb_store import KBStore


def _tmp_db() -> Path:
    return Path(tempfile.mktemp(suffix=".db"))


def _make_conversation(turns: list[ChatTurn]) -> Conversation:
    return Conversation(
        conversation_id="test-conv",
        category="Testing",
        title="Test Conversation",
        sessions=[turns],
        probing_questions={cat: [] for cat in QuestionCategory},
    )


class TestClaimDetection:
    def test_detects_user_claims(self) -> None:
        assert _is_factual_claim("I have never used Flask before")
        assert _is_factual_claim("I started working on the project last week")
        assert _is_factual_claim("My deadline is next Friday")

    def test_rejects_non_claims(self) -> None:
        assert not _is_factual_claim("How do I install Python?")
        assert not _is_factual_claim("Thanks for the help!")
        assert not _is_factual_claim("Here is the code output")

    def test_extract_claim(self) -> None:
        text = "I have never used Flask before. Can you help me set it up?"
        claim = _extract_claim(text)
        assert "never used Flask" in claim


class TestContradictionDetection:
    def test_negation_overlap(self) -> None:
        assert _has_negation_overlap(
            "I have never written Flask routes",
            "I implemented a Flask homepage route",
        )

    def test_no_contradiction_different_topics(self) -> None:
        assert not _has_negation_overlap(
            "I don't like pizza",
            "I implemented a Flask homepage route",
        )

    def test_no_contradiction_same_polarity(self) -> None:
        assert not _has_negation_overlap(
            "I have used Flask before",
            "I implemented a Flask homepage route",
        )


class TestConversationIngestionKB:
    def test_ingest_creates_chunks_and_claims(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                turns = [
                    ChatTurn("I have never used Flask before", 1, "1,1", "q", "user", "March-15"),
                    ChatTurn("Flask is a micro web framework", 2, "1,2", "q", "assistant", ""),
                    ChatTurn("My deadline is next Friday", 3, "1,3", "q", "user", "March-16"),
                ]
                conv = _make_conversation(turns)
                stats = ingest_conversation_kb(conv, store)

                assert stats["chunks"] == 3
                assert stats["claims"] >= 1  # At least user claims detected
        finally:
            db.unlink(missing_ok=True)

    def test_ingest_detects_supersession(self) -> None:
        db = _tmp_db()
        try:
            with KBStore(db) as store:
                turns = [
                    ChatTurn(
                        "I have never written any Flask routes or handled HTTP requests",
                        1,
                        "1,1",
                        "q",
                        "user",
                        "March-15",
                    ),
                    ChatTurn("Let me help you with Flask", 2, "1,2", "q", "assistant", ""),
                    ChatTurn(
                        "I actually implemented a basic Flask homepage route yesterday",
                        3,
                        "2,1",
                        "q",
                        "user",
                        "March-20",
                    ),
                ]
                conv = _make_conversation(turns)
                stats = ingest_conversation_kb(conv, store)

                # Should detect the contradiction and create a supersession.
                assert stats["supersessions"] >= 1
                # Active conclusions should only have the latest version.
                active = store.get_active_conclusions()
                claims = [str(c["claim"]) for c in active]
                assert not any("never written" in c for c in claims)
        finally:
            db.unlink(missing_ok=True)


class TestConversationIngestionFlat:
    def test_ingest_all_turns(self) -> None:
        with FlatStore() as store:
            turns = [
                ChatTurn("Turn one", 1, "1,1", "q", "user", "March-15"),
                ChatTurn("Turn two", 2, "1,2", "q", "assistant", ""),
                ChatTurn("Turn three", 3, "1,3", "q", "user", "March-16"),
            ]
            conv = _make_conversation(turns)
            count = ingest_conversation_flat(conv, store)
            assert count == 3
            assert store.count() == 3

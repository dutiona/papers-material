"""Tests for BEAM dataset loading."""

from __future__ import annotations

import pytest

from dataset.loader import load_beam, load_experiment_questions
from dataset.types import (
    EXPERIMENT_CATEGORIES,
    Conversation,
    ProbingQuestion,
    QuestionCategory,
)


@pytest.fixture(scope="module")
def conversations() -> list[Conversation]:
    """Load BEAM 100K once for all tests in this module."""
    return load_beam("100K")


class TestLoadBeam:
    def test_loads_correct_count(self, conversations: list[Conversation]) -> None:
        assert len(conversations) == 20

    def test_conversation_has_sessions(self, conversations: list[Conversation]) -> None:
        conv = conversations[0]
        assert len(conv.sessions) == 3
        assert all(len(session) > 0 for session in conv.sessions)

    def test_conversation_has_all_categories(self, conversations: list[Conversation]) -> None:
        conv = conversations[0]
        for cat in QuestionCategory:
            assert cat in conv.probing_questions, f"Missing category: {cat}"
            assert len(conv.probing_questions[cat]) == 2

    def test_turns_have_required_fields(self, conversations: list[Conversation]) -> None:
        turn = conversations[0].sessions[0][0]
        assert turn.content
        assert turn.role in ("user", "assistant")
        assert turn.index

    def test_experiment_questions_have_ideal_answer(
        self, conversations: list[Conversation]
    ) -> None:
        """Experiment categories (contradiction + temporal) must have ideal answers."""
        for conv in conversations:
            for q in conv.experiment_questions:
                assert q.ideal_answer, (
                    f"Empty ideal_answer in {q.category} for conv {conv.conversation_id}"
                )

    def test_probing_question_category_matches(self, conversations: list[Conversation]) -> None:
        for conv in conversations:
            for cat, questions in conv.probing_questions.items():
                for q in questions:
                    assert q.category == cat


class TestExperimentSubset:
    def test_experiment_questions_count(self, conversations: list[Conversation]) -> None:
        questions = [q for conv in conversations for q in conv.experiment_questions]
        assert len(questions) == 80  # 20 convs × 2 categories × 2 questions

    def test_only_target_categories(self, conversations: list[Conversation]) -> None:
        questions = [q for conv in conversations for q in conv.experiment_questions]
        categories = {q.category for q in questions}
        assert categories == EXPERIMENT_CATEGORIES

    def test_load_experiment_questions_shortcut(self) -> None:
        questions = load_experiment_questions("100K")
        assert len(questions) == 80
        assert all(isinstance(q, ProbingQuestion) for q in questions)

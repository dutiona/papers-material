"""Tests for the query classifier."""

from __future__ import annotations

from classifier.router import RouterMode, classify, classify_heuristic, classify_oracle
from dataset.types import ProbingQuestion, QueryRoute, QuestionCategory


def _make_question(text: str, category: QuestionCategory) -> ProbingQuestion:
    return ProbingQuestion(
        question=text,
        ideal_answer="dummy",
        category=category,
        conversation_id="test",
    )


class TestOracleRouter:
    def test_contradiction_routes_to_knowledge(self) -> None:
        q = _make_question("anything", QuestionCategory.CONTRADICTION_RESOLUTION)
        assert classify_oracle(q) == QueryRoute.KNOWLEDGE

    def test_temporal_routes_to_memory(self) -> None:
        q = _make_question("anything", QuestionCategory.TEMPORAL_REASONING)
        assert classify_oracle(q) == QueryRoute.MEMORY

    def test_other_categories_route_to_mixed(self) -> None:
        q = _make_question("anything", QuestionCategory.SUMMARIZATION)
        assert classify_oracle(q) == QueryRoute.MIXED


class TestHeuristicRouter:
    def test_temporal_keywords(self) -> None:
        q = _make_question(
            "How many days between my first meeting and the deadline?",
            QuestionCategory.TEMPORAL_REASONING,
        )
        assert classify_heuristic(q) == QueryRoute.MEMORY

    def test_contradiction_keywords(self) -> None:
        q = _make_question(
            "Have I ever worked with Flask routes in this project?",
            QuestionCategory.CONTRADICTION_RESOLUTION,
        )
        assert classify_heuristic(q) == QueryRoute.KNOWLEDGE

    def test_ambiguous_defaults_to_mixed(self) -> None:
        q = _make_question(
            "Tell me about my project setup",
            QuestionCategory.INFORMATION_EXTRACTION,
        )
        assert classify_heuristic(q) == QueryRoute.MIXED


class TestClassifyDispatch:
    def test_oracle_mode(self) -> None:
        q = _make_question("anything", QuestionCategory.TEMPORAL_REASONING)
        assert classify(q, RouterMode.ORACLE) == QueryRoute.MEMORY

    def test_heuristic_mode(self) -> None:
        q = _make_question(
            "How many weeks until the deadline?",
            QuestionCategory.TEMPORAL_REASONING,
        )
        assert classify(q, RouterMode.HEURISTIC) == QueryRoute.MEMORY

"""Tests for the evaluation scoring parser."""

from __future__ import annotations

from evaluation.llm import _parse_score_response


class TestParseScoreResponse:
    def test_perfect_format(self) -> None:
        text = "SCORE: 4\nJUSTIFICATION: Perfect answer with all required elements."
        score, justification = _parse_score_response(text)
        assert score == 1.0
        assert "Perfect answer" in justification

    def test_zero_score(self) -> None:
        text = "SCORE: 0\nJUSTIFICATION: Completely off-topic."
        score, justification = _parse_score_response(text)
        assert score == 0.0
        assert "off-topic" in justification

    def test_partial_credit(self) -> None:
        text = "SCORE: 2\nJUSTIFICATION: Identifies inconsistency but misses one side."
        score, _ = _parse_score_response(text)
        assert score == 0.5

    def test_all_valid_scores(self) -> None:
        expected = {0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}
        for raw, normalized in expected.items():
            text = f"SCORE: {raw}\nJUSTIFICATION: test"
            score, _ = _parse_score_response(text)
            assert score == normalized, f"Raw {raw} should map to {normalized}, got {score}"

    def test_extra_whitespace(self) -> None:
        text = "  SCORE:  3  \n  JUSTIFICATION:  Good but not perfect.  "
        score, justification = _parse_score_response(text)
        assert score == 0.75
        assert "Good but not perfect" in justification

    def test_model_adds_preamble(self) -> None:
        text = "Let me analyze this...\n\nSCORE: 2\nJUSTIFICATION: Partial match."
        score, _ = _parse_score_response(text)
        assert score == 0.5

    def test_model_adds_code_fences(self) -> None:
        text = "```\nSCORE: 3\nJUSTIFICATION: Good answer.\n```"
        score, _ = _parse_score_response(text)
        assert score == 0.75

    def test_fallback_recovers_bare_integer(self) -> None:
        text = "The score is 3 because the answer is mostly correct."
        score, _ = _parse_score_response(text)
        assert score == 0.75

    def test_garbage_returns_zero_with_error(self) -> None:
        text = "I cannot evaluate this question."
        score, justification = _parse_score_response(text)
        assert score == 0.0
        assert "PARSE_ERROR" in justification

    def test_empty_input(self) -> None:
        score, justification = _parse_score_response("")
        assert score == 0.0
        assert "PARSE_ERROR" in justification

    def test_missing_justification_still_parses_score(self) -> None:
        text = "SCORE: 4"
        score, justification = _parse_score_response(text)
        assert score == 1.0
        assert justification == ""

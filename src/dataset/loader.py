"""Load and parse the BEAM dataset from HuggingFace."""

from __future__ import annotations

import ast
import logging
from typing import Any

from datasets import load_dataset  # type: ignore[import-untyped]

from .types import (
    EXPERIMENT_CATEGORIES,
    ChatTurn,
    Conversation,
    ProbingQuestion,
    QuestionCategory,
)

logger = logging.getLogger(__name__)

# HuggingFace dataset identifiers.
_HF_REPO = "Mohammadta/BEAM"
_HF_REPO_10M = "Mohammadta/BEAM-10M"

# BEAM splits available.
VALID_SPLITS = ("100K", "500K", "1M")


def _parse_turn(raw: dict[str, Any]) -> ChatTurn:
    return ChatTurn(
        content=str(raw["content"]),
        turn_id=int(raw["id"]),
        index=str(raw["index"]),
        question_type=str(raw["question_type"]),
        role=str(raw["role"]),
        time_anchor=str(raw.get("time_anchor", "")),
    )


def _parse_probing_questions(
    raw_str: str, conversation_id: str
) -> dict[QuestionCategory, list[ProbingQuestion]]:
    parsed: dict[str, list[dict[str, Any]]] = ast.literal_eval(raw_str)
    result: dict[QuestionCategory, list[ProbingQuestion]] = {}

    for cat_str, questions in parsed.items():
        try:
            cat = QuestionCategory(cat_str)
        except ValueError:
            logger.warning("Unknown probing question category: %s", cat_str)
            continue

        pqs: list[ProbingQuestion] = []
        for q in questions:
            # BEAM uses 'ideal_answer' for some categories, 'answer' for others.
            ideal = str(q.get("ideal_answer") or q.get("answer") or q.get("ideal_response", ""))
            pqs.append(
                ProbingQuestion(
                    question=str(q["question"]),
                    ideal_answer=ideal,
                    category=cat,
                    conversation_id=conversation_id,
                    difficulty=str(q.get("difficulty", "")),
                    metadata={
                        k: v
                        for k, v in q.items()
                        if k
                        not in (
                            "question",
                            "ideal_answer",
                            "answer",
                            "ideal_response",
                            "difficulty",
                        )
                    },
                )
            )
        result[cat] = pqs

    return result


def _parse_conversation(row: dict[str, Any]) -> Conversation:
    conv_id = str(row["conversation_id"])
    seed = row["conversation_seed"]

    # Chat is a list of sessions, each session a list of turn dicts.
    sessions: list[list[ChatTurn]] = []
    for session_turns in row["chat"]:
        sessions.append([_parse_turn(t) for t in session_turns])

    probing = _parse_probing_questions(str(row["probing_questions"]), conv_id)

    return Conversation(
        conversation_id=conv_id,
        category=str(seed.get("category", "")),
        title=str(seed.get("title", "")),
        sessions=sessions,
        probing_questions=probing,
    )


def load_beam(split: str = "100K") -> list[Conversation]:
    """Load the BEAM dataset from HuggingFace and parse into typed structures.

    Args:
        split: One of "100K", "500K", "1M". Defaults to "100K" (smallest, 20 conversations).

    Returns:
        List of parsed Conversation objects.
    """
    if split not in VALID_SPLITS:
        msg = f"Invalid split '{split}'. Choose from {VALID_SPLITS}"
        raise ValueError(msg)

    logger.info("Loading BEAM dataset (split=%s) from HuggingFace...", split)
    ds = load_dataset(_HF_REPO, split=split)  # pyright: ignore[reportUnknownVariableType]
    rows: list[dict[str, Any]] = [dict(row) for row in ds]  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType]
    conversations = [_parse_conversation(row) for row in rows]
    logger.info("Loaded %d conversations", len(conversations))
    return conversations


def load_experiment_questions(split: str = "100K") -> list[ProbingQuestion]:
    """Load only the contradiction-resolution and temporal-reasoning questions.

    Convenience function for the pilot experiment.
    """
    conversations = load_beam(split)
    questions: list[ProbingQuestion] = []
    for conv in conversations:
        questions.extend(conv.experiment_questions)

    by_cat = {cat: sum(1 for q in questions if q.category == cat) for cat in EXPERIMENT_CATEGORIES}
    logger.info("Experiment questions: %s (total=%d)", dict(by_cat), len(questions))
    return questions

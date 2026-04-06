"""Data types for the BEAM pilot experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class QuestionCategory(StrEnum):
    """BEAM probing question categories."""

    ABSTENTION = "abstention"
    CONTRADICTION_RESOLUTION = "contradiction_resolution"
    EVENT_ORDERING = "event_ordering"
    INFORMATION_EXTRACTION = "information_extraction"
    INSTRUCTION_FOLLOWING = "instruction_following"
    KNOWLEDGE_UPDATE = "knowledge_update"
    MULTI_SESSION_REASONING = "multi_session_reasoning"
    PREFERENCE_FOLLOWING = "preference_following"
    SUMMARIZATION = "summarization"
    TEMPORAL_REASONING = "temporal_reasoning"


# The two categories this experiment targets.
EXPERIMENT_CATEGORIES = frozenset(
    {
        QuestionCategory.CONTRADICTION_RESOLUTION,
        QuestionCategory.TEMPORAL_REASONING,
    }
)


class QueryRoute(StrEnum):
    """Where a query should be routed."""

    KNOWLEDGE = "knowledge"  # → knowledge-base (supersession-aware)
    MEMORY = "memory"  # → memory-engine (bi-temporal)
    MIXED = "mixed"  # → both, merge results


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """A single turn in a BEAM conversation."""

    content: str
    turn_id: int
    index: str  # e.g. "1,1" — session, turn within session
    question_type: str  # "main_question", "follow_up", etc.
    role: str  # "user" or "assistant"
    time_anchor: str  # e.g. "March-15"


@dataclass(frozen=True, slots=True)
class ProbingQuestion:
    """A BEAM probing question with its ideal answer and metadata."""

    question: str
    ideal_answer: str
    category: QuestionCategory
    conversation_id: str
    difficulty: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())


@dataclass(frozen=True, slots=True)
class Conversation:
    """A full BEAM conversation: chat history + probing questions."""

    conversation_id: str
    category: str  # topic category (e.g. "Coding")
    title: str
    sessions: list[list[ChatTurn]]  # 3 sessions of turns
    probing_questions: dict[QuestionCategory, list[ProbingQuestion]]

    @property
    def all_turns(self) -> list[ChatTurn]:
        """Flatten all sessions into a single chronological list of turns."""
        return [turn for session in self.sessions for turn in session]

    @property
    def experiment_questions(self) -> list[ProbingQuestion]:
        """Only contradiction-resolution and temporal-reasoning questions."""
        result: list[ProbingQuestion] = []
        for cat in EXPERIMENT_CATEGORIES:
            result.extend(self.probing_questions.get(cat, []))
        return result

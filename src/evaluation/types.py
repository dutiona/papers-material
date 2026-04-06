"""Evaluation data types."""

from __future__ import annotations

from dataclasses import dataclass

from dataset.types import QuestionCategory, QueryRoute


@dataclass(frozen=True, slots=True)
class TrialResult:
    """Result of a single probing-question trial."""

    question_text: str
    ideal_answer: str
    generated_answer: str
    retrieved_context: str
    category: QuestionCategory
    route: QueryRoute
    conversation_id: str
    condition: str  # "typed" or "flat"
    score: float  # 0.0 to 1.0
    justification: str  # LLM judge reasoning


@dataclass(slots=True)
class ExperimentReport:
    """Aggregate results for one experiment run."""

    trials: list[TrialResult]

    @property
    def contradiction_scores(self) -> list[float]:
        return [
            t.score for t in self.trials if t.category == QuestionCategory.CONTRADICTION_RESOLUTION
        ]

    @property
    def temporal_scores(self) -> list[float]:
        return [t.score for t in self.trials if t.category == QuestionCategory.TEMPORAL_REASONING]

    def mean_by_category(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for cat in (QuestionCategory.CONTRADICTION_RESOLUTION, QuestionCategory.TEMPORAL_REASONING):
            scores = [t.score for t in self.trials if t.category == cat]
            result[cat.value] = sum(scores) / len(scores) if scores else 0.0
        return result

    def mean_by_condition(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for cond in ("typed", "flat"):
            scores = [t.score for t in self.trials if t.condition == cond]
            result[cond] = sum(scores) / len(scores) if scores else 0.0
        return result

    def mean_by_category_and_condition(self) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for cat in (QuestionCategory.CONTRADICTION_RESOLUTION, QuestionCategory.TEMPORAL_REASONING):
            result[cat.value] = {}
            for cond in ("typed", "flat"):
                scores = [t.score for t in self.trials if t.category == cat and t.condition == cond]
                result[cat.value][cond] = sum(scores) / len(scores) if scores else 0.0
        return result

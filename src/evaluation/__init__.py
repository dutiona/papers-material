"""Evaluation pipeline: answer generation and scoring."""

from .llm import generate_answer, score_answer
from .types import ExperimentReport, TrialResult

__all__ = ["ExperimentReport", "TrialResult", "generate_answer", "score_answer"]

"""Query classifier: routes probing questions to the appropriate store.

Two modes:
- Oracle: uses BEAM ground-truth labels (isolates architecture effect from routing errors)
- Heuristic: keyword-based classification (measures end-to-end realism)
"""

from __future__ import annotations

import re
from enum import StrEnum

from dataset.types import ProbingQuestion, QueryRoute, QuestionCategory


class RouterMode(StrEnum):
    ORACLE = "oracle"
    HEURISTIC = "heuristic"


# Patterns that suggest temporal reasoning queries.
_TEMPORAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"how (?:many|long|much time)",
        r"(?:days?|weeks?|months?|hours?) (?:between|since|until|before|after|from)",
        r"when did",
        r"what (?:date|time|day)",
        r"(?:before|after|during|since|until) (?:the|my|our|I)",
        r"(?:first|last|earliest|latest|most recent)",
        r"(?:timeline|chronolog|sequence of events|order of)",
        r"how (?:old|recent)",
    ]
]

# Patterns that suggest contradiction resolution queries.
_CONTRADICTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(?:contradict|inconsisten|conflict)",
        r"(?:you said|I said|mentioned|stated) .{0,30} (?:but|however|yet|although)",
        r"(?:have I|did I|do I) (?:ever|really|actually)",
        r"(?:changed? my mind|correct(?:ed)?|updated?|revised?)",
        r"which (?:is|was) (?:correct|true|right|accurate)",
    ]
]


def classify_oracle(question: ProbingQuestion) -> QueryRoute:
    """Route based on BEAM ground-truth category labels."""
    if question.category == QuestionCategory.CONTRADICTION_RESOLUTION:
        return QueryRoute.KNOWLEDGE
    if question.category == QuestionCategory.TEMPORAL_REASONING:
        return QueryRoute.MEMORY
    return QueryRoute.MIXED


def classify_heuristic(question: ProbingQuestion) -> QueryRoute:
    """Route based on keyword patterns in the question text."""
    text = question.question

    temporal_score = sum(1 for p in _TEMPORAL_PATTERNS if p.search(text))
    contradiction_score = sum(1 for p in _CONTRADICTION_PATTERNS if p.search(text))

    if temporal_score > contradiction_score:
        return QueryRoute.MEMORY
    if contradiction_score > temporal_score:
        return QueryRoute.KNOWLEDGE
    if temporal_score > 0:
        return QueryRoute.MIXED
    # Default: route to both when uncertain.
    return QueryRoute.MIXED


def classify(question: ProbingQuestion, mode: RouterMode = RouterMode.ORACLE) -> QueryRoute:
    """Classify a probing question and return its routing decision."""
    if mode == RouterMode.ORACLE:
        return classify_oracle(question)
    return classify_heuristic(question)

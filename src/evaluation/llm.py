"""LLM interface for answer generation and scoring via Ollama.

The scoring prompt was designed via a 3-round structured debate between
Claude Opus 4.6, Codex gpt-5.4, and Gemini 3.1-pro. See doc/debate-scoring-prompt/
for the full deliberation record.
"""

from __future__ import annotations

import logging
import re

import ollama

from dataset.types import QuestionCategory

logger = logging.getLogger(__name__)

# Defaults — override via function args.
DEFAULT_MODEL = "gemma3:27b"
DEFAULT_EMBED_MODEL = "all-minilm:l6-v2"

# Valid discrete score buckets (0-4 integer, normalized to 0.0-1.0).
_VALID_SCORES = {0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}

_SCORING_PROMPT = """\
You are grading one generated answer against one ideal answer for a research benchmark.

Your task is to assign exactly one integer score and one short justification.

Return EXACTLY these two lines and nothing else:
SCORE: <0 or 1 or 2 or 3 or 4>
JUSTIFICATION: <one sentence>

Do not use JSON.
Do not use markdown.
Do not output any analysis.
Do not output any extra text.

Before writing the score, silently compare the generated answer against the ideal \
answer and determine which required elements are present, missing, or wrong. \
Do not print this reasoning.

General rules:
- Judge semantic correctness, not wording overlap.
- Use only the category, question, ideal answer, and generated answer below.
- Prefer the lower score when uncertain.
- Empty, irrelevant, or content-free answers score 0.
- Fluent wording does not earn credit if the core content is wrong.

If CATEGORY is contradiction_resolution:
- 4: clearly states there is a contradiction or inconsistency, captures both \
conflicting claims or their substance, and asks for clarification or explicitly \
refuses to choose a side.
- 3: clearly states there is a contradiction or inconsistency and captures both \
sides, but the clarification or neutrality step is weaker than ideal.
- 2: identifies inconsistency but omits one side, describes the conflict vaguely, \
or mixes clarification with premature resolution.
- 1: weak hint of uncertainty or mismatch, but no clear contradiction is framed \
between two claims.
- 0: misses the contradiction, chooses one side as settled without clearly flagging \
a contradiction, or is off-topic.

Hard caps for contradiction_resolution:
- If both conflicting sides are not represented, the score cannot exceed 2.
- If the answer chooses one side as settled, the score cannot exceed 2.
- If the answer chooses one side as settled without clearly flagging a contradiction, \
the score must be 0.

If CATEGORY is temporal_reasoning:
- 4: correct final temporal conclusion with correct dates, ordering, duration, and units.
- 3: correct final conclusion with one minor missing supporting detail.
- 2: partially correct setup or method, but the final number, ordering, unit, or \
conclusion is wrong or incomplete.
- 1: mentions relevant dates or time concepts but the reasoning is mostly unsupported \
or wrong.
- 0: no meaningful temporal reasoning, wrong answer, empty answer, or off-topic.

Hard caps for temporal_reasoning:
- If the final numeric or ordering conclusion is wrong, the score cannot exceed 2.
- If the answer gives no concrete temporal support when the ideal answer depends on \
dates, durations, or ordering, the score cannot exceed 1.

CATEGORY:
{category}

Question:
{question}

Ideal answer:
{ideal_answer}

Generated answer:
{generated_answer}"""

_SCORE_RE = re.compile(r"(?im)^\s*SCORE:\s*([0-4])\s*$")
_JUSTIFICATION_RE = re.compile(r"(?im)^\s*JUSTIFICATION:\s*(.+?)\s*$")
_FALLBACK_SCORE_RE = re.compile(r"\b([0-4])\b")


def _parse_score_response(text: str) -> tuple[float, str]:
    """Parse the LLM judge response into (normalized_score, justification).

    Strategy: strict regex first, fallback to first integer in [0-4], hard failure
    returns 0.0 with error flag.
    """
    # Primary: strict format.
    score_match = _SCORE_RE.search(text)
    justification_match = _JUSTIFICATION_RE.search(text)

    if score_match:
        raw = int(score_match.group(1))
        justification = justification_match.group(1) if justification_match else ""
        return _VALID_SCORES.get(raw, 0.0), justification

    # Fallback: strip code fences and find first integer near a SCORE marker.
    cleaned = re.sub(r"```\w*\n?", "", text)
    fallback_match = _FALLBACK_SCORE_RE.search(cleaned)
    if fallback_match:
        raw = int(fallback_match.group(1))
        logger.warning("Malformed judge output, recovered score=%d from: %s", raw, text[:200])
        return _VALID_SCORES.get(raw, 0.0), justification_match.group(
            1
        ) if justification_match else ""

    # Hard failure.
    logger.error("Could not parse judge output: %s", text[:200])
    return 0.0, f"PARSE_ERROR: {text[:160]}"


def generate_answer(
    question: str,
    context: str,
    *,
    model: str = DEFAULT_MODEL,
) -> str:
    """Generate an answer to a probing question given retrieved context."""
    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant answering questions about a conversation. "
                    "Use ONLY the provided context to answer. If the context contains "
                    "contradictory information, explicitly identify the contradiction "
                    "and ask for clarification. If temporal information is present, "
                    "use it for date/time calculations."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ],
    )
    return str(response.message.content)


def score_answer(
    question: str,
    ideal_answer: str,
    generated_answer: str,
    category: QuestionCategory,
    *,
    model: str = DEFAULT_MODEL,
) -> tuple[float, str]:
    """Score a generated answer against the ideal using an LLM judge.

    Uses a unified prompt with category-specific rubrics and hard caps.
    Designed for local models (gemma3 27b) — discrete 0-4 integer scale,
    two-line output format, tolerant fallback parsing.

    Args:
        question: The original probing question.
        ideal_answer: The BEAM-provided ideal answer.
        generated_answer: The system-generated answer.
        category: The BEAM question category (determines which rubric applies).
        model: Ollama model name.

    Returns:
        Tuple of (score: float 0.0-1.0, justification: str).
    """
    prompt = _SCORING_PROMPT.format(
        category=category.value,
        question=question,
        ideal_answer=ideal_answer,
        generated_answer=generated_answer or "(empty answer)",
    )

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )
        raw_output = str(response.message.content)
    except Exception:
        logger.exception("Ollama call failed for scoring")
        return 0.0, "OLLAMA_ERROR"

    return _parse_score_response(raw_output)

"""LLM interface for answer generation and scoring via Ollama."""

from __future__ import annotations

import logging

import ollama

logger = logging.getLogger(__name__)

# Defaults — override via function args.
DEFAULT_MODEL = "gemma3:27b"
DEFAULT_EMBED_MODEL = "all-minilm:l6-v2"


def generate_answer(
    question: str,
    context: str,
    *,
    model: str = DEFAULT_MODEL,
) -> str:
    """Generate an answer to a probing question given retrieved context.

    Args:
        question: The probing question.
        context: Retrieved facts/chunks concatenated as context.
        model: Ollama model name.

    Returns:
        The generated answer text.
    """
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


# TODO(user): Implement the scoring prompt.
# This is where your judgment matters — see the function docstring for guidance.
def score_answer(
    question: str,
    ideal_answer: str,
    generated_answer: str,
    *,
    model: str = DEFAULT_MODEL,
) -> tuple[float, str]:
    """Score a generated answer against the ideal answer using an LLM judge.

    This function determines how we measure success. The prompt must:
    1. Return a score between 0.0 and 1.0
    2. Return a brief justification

    Trade-offs to consider:
    - Strict nugget matching (BEAM-style): parse ideal into atomic facts, check each.
      More granular but requires reliable extraction from the LLM.
    - Holistic scoring: ask the LLM to judge overall quality on a scale.
      Simpler but coarser.
    - For contradiction questions: does the answer DETECT the contradiction?
      Partial credit for identifying inconsistency even if resolution is wrong?
    - For temporal questions: does the answer get the calculation RIGHT?
      Should a wrong number with correct method get partial credit?

    Args:
        question: The original probing question.
        ideal_answer: The BEAM-provided ideal answer.
        generated_answer: The system-generated answer.
        model: Ollama model name.

    Returns:
        Tuple of (score: float 0-1, justification: str).
    """
    raise NotImplementedError(
        "Implement score_answer() in src/evaluation/llm.py — "
        "see docstring for guidance on the scoring prompt design."
    )

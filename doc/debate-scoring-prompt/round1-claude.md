# Round 1 — Claude (Opus 4.6)

## Approach: Unified Holistic with Category-Aware Rubric

I propose a **single prompt** that works for both categories but includes category-specific rubric criteria. Rationale:

- **Against nugget-based**: Gemma3 27b is not reliable enough for multi-step extraction (extract nuggets → check each → aggregate). Every additional structured step is a failure point on a local model.
- **Against fully separate prompts**: Two prompts doubles maintenance and makes cross-category score comparison harder. A unified prompt with conditional rubric criteria keeps scores on the same scale.
- **For structured output**: Use a strict JSON output format with fallback parsing. The prompt explicitly demonstrates the format.

## The Prompt

```
You are an evaluator judging how well a generated answer matches an ideal answer for a memory benchmark question.

CATEGORY: {category}
QUESTION: {question}
IDEAL ANSWER: {ideal_answer}
GENERATED ANSWER: {generated_answer}

SCORING RUBRIC (0-4 scale):

For CONTRADICTION RESOLUTION questions:
- 4: Correctly identifies the contradiction, cites both conflicting statements, and requests clarification
- 3: Identifies the contradiction and cites at least one conflicting statement
- 2: Acknowledges inconsistency but does not pinpoint the specific conflicting statements
- 1: Gives a definitive answer without acknowledging any contradiction
- 0: Completely off-topic, empty, or factually wrong about the conversation content

For TEMPORAL REASONING questions:
- 4: Correct final answer with correct dates/durations and correct calculation method
- 3: Correct method and dates but minor arithmetic error (off by 1 day/week)
- 2: Correct dates referenced but wrong calculation or wrong units
- 1: Attempts temporal reasoning but with wrong dates or completely wrong method
- 0: Completely off-topic, empty, or no temporal reasoning attempted

Respond with EXACTLY this JSON format, nothing else:
{"score": <0-4>, "justification": "<one sentence explaining the score>"}
```

## Parsing Strategy

```python
import json
import re

def parse_score_response(text: str) -> tuple[float, str]:
    # Try direct JSON parse first
    try:
        obj = json.loads(text.strip())
        score = max(0.0, min(4.0, float(obj["score"])))
        return score / 4.0, str(obj.get("justification", ""))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # Fallback: regex for score pattern
    m = re.search(r'"score"\s*:\s*(\d+)', text)
    if m:
        score = max(0, min(4, int(m.group(1))))
        justification_m = re.search(r'"justification"\s*:\s*"([^"]*)"', text)
        justification = justification_m.group(1) if justification_m else ""
        return score / 4.0, justification

    # Last resort: return 0 with error flag
    return 0.0, f"PARSE_ERROR: {text[:200]}"
```

Key: normalize 0-4 integer scale to 0.0-1.0 float. Integer scale is easier for the local model to produce reliably than a continuous float.

## Partial Credit

**Contradiction**: The 4-point scale naturally captures partial credit:

- Detecting "something is off" without specifics = 2/4 = 0.5
- Identifying the contradiction but missing one side = 3/4 = 0.75

**Temporal**: The scale distinguishes method from answer:

- Right approach, wrong number = 3/4 = 0.75 (method matters more than arithmetic)
- Right dates, wrong calculation = 2/4 = 0.5

## Failure Modes

1. **Garbage output**: Regex fallback catches most malformed JSON. Last resort returns 0.0 with PARSE_ERROR flag so we can filter/inspect.
2. **Score inflation**: Local models tend to be generous. The rubric anchors specific behaviors to specific scores — "cites both conflicting statements" is binary, not subjective.
3. **Category bleed**: The rubric is conditional on `{category}`, so the model knows which criteria to apply.
4. **Empty generated answer**: Rubric explicitly scores this as 0 ("empty").

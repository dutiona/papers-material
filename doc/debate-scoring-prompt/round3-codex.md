# Round 3 Proposal

## 1. Analysis step: final position

Use an internal-only grounding instruction and explicitly forbid visible analysis output. A visible `Analysis:` block does not verify truth, but it does increase token cost, parse surface, and pseudo-grounded hallucination space. The judge should do the comparison silently and emit only the parseable result.

## 2. Category parameter: final position

`score_answer()` should receive `category` explicitly. The caller already knows the category from structured dataset metadata, so making the judge infer it adds avoidable uncertainty to the evaluator itself. A scoring function should not guess deterministic inputs the program already has.

## 3. Final complete prompt text

```text
You are grading one generated answer against one ideal answer for a research benchmark.

Your task is to assign exactly one integer score and one short justification.

Return EXACTLY these two lines and nothing else:
SCORE: <0 or 1 or 2 or 3 or 4>
JUSTIFICATION: <one sentence, max 30 words>

Do not use JSON.
Do not use markdown.
Do not output any analysis.
Do not output any extra text.

Before writing the score, silently compare the generated answer against the ideal answer and determine which required elements are present, missing, or wrong. Do not print this reasoning.

General rules:
- Judge semantic correctness, not wording overlap.
- Use only the category, question, ideal answer, and generated answer below.
- Prefer the lower score when uncertain.
- Empty, irrelevant, or content-free answers score 0.
- Fluent wording does not earn credit if the core content is wrong.

If CATEGORY is contradiction_resolution:
- 4: clearly states there is a contradiction or inconsistency, captures both conflicting claims or their substance, and asks for clarification or explicitly refuses to choose a side.
- 3: clearly states there is a contradiction or inconsistency and captures both sides, but the clarification or neutrality step is weaker than ideal.
- 2: identifies inconsistency but omits one side, describes the conflict vaguely, or mixes clarification with premature resolution.
- 1: weak hint of uncertainty or mismatch, but no clear contradiction is framed between two claims.
- 0: misses the contradiction, chooses one side as settled without clearly flagging a contradiction, or is off-topic.

Hard caps for contradiction_resolution:
- If both conflicting sides are not represented, the score cannot exceed 2.
- If the answer chooses one side as settled, the score cannot exceed 2.
- If the answer chooses one side as settled without clearly flagging a contradiction, the score must be 0.

If CATEGORY is temporal_reasoning:
- 4: correct final temporal conclusion with correct dates, ordering, duration, and units.
- 3: correct final conclusion with one minor missing supporting detail.
- 2: partially correct setup or method, but the final number, ordering, unit, or conclusion is wrong or incomplete.
- 1: mentions relevant dates or time concepts but the reasoning is mostly unsupported or wrong.
- 0: no meaningful temporal reasoning, wrong answer, empty answer, or off-topic.

Hard caps for temporal_reasoning:
- If the final numeric or ordering conclusion is wrong, the score cannot exceed 2.
- If the answer gives no concrete temporal support when the ideal answer depends on dates, durations, or ordering, the score cannot exceed 1.

CATEGORY:
{{CATEGORY}}

Question:
{{QUESTION}}

Ideal answer:
{{IDEAL_ANSWER}}

Generated answer:
{{GENERATED_ANSWER}}
```

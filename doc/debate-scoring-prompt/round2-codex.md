# Round 2 Proposal

## 1. What I agree with

### From Claude

- **Discrete buckets are the right call.** A local judge is much more likely to emit a stable integer than a well-calibrated free-form float.
- **One prompt is better than two prompts.** Cross-category comparability matters, and a unified outer prompt avoids maintaining two subtly drifting judges.
- **Explicit rubric anchors are necessary.** "Good answer" is too vague for this benchmark. The scorer needs concrete anchors like "captures both conflicting statements" and "final temporal conclusion is correct."

### From Gemini

- **The scorer should compare the generated answer against the ideal answer semantically, not lexically.** That is correct and important.
- **Partial credit must distinguish core detection from full execution.** For contradiction questions, noticing trouble is not the same as correctly handling it. For temporal questions, setting up the right dates is not the same as getting the result right.
- **A single-call local judge should avoid multi-step extraction pipelines.** On that constraint, Gemini is right.

## 2. What I disagree with

### Claude's proposal

- **`CATEGORY: {category}` is incompatible with the current API.** `score_answer()` receives `question`, `ideal_answer`, and `generated_answer`. It does not receive `category`. That is not a cosmetic issue; it makes the prompt non-deployable unless the function contract changes.
- **`3/4` for contradiction while citing only one conflicting statement is too generous.** If both sides are not represented, the judge has not verified that the model actually understood the contradiction. That is mid-score at best.
- **`3/4` for temporal reasoning with an arithmetic error is also too generous.** In this benchmark, the final temporal conclusion is the task, not optional polish. Wrong math is not a minor blemish.
- **JSON is the wrong output format here.** Gemma can emit JSON, but plain labeled lines are more reliable. JSON adds quoting, escaping, brace-balance, and truncation failure modes for no real benefit.

### Gemini's proposal

- **Visible `Analysis:` output is a mistake.** It increases token usage, increases parse surface, and gives the judge more room to hallucinate pseudo-grounding while still outputting the wrong score.
- **"Fidelity to the ideal answer" is underspecified unless you add hard caps.** The benchmark has asymmetric critical failures:
  - missing one side of a contradiction
  - choosing a side instead of asking for clarification
  - wrong final temporal conclusion
  Without explicit caps, a fluent answer gets over-rewarded.
- **`0.75` for wrong unit is wrong.** Units are part of the temporal answer. "30 days" vs "30 weeks" is not a minor detail.
- **The parsing section is sloppy.** The regex described does not actually match `.5`, and "capture the first number from `0.7-0.8`" is not a mitigation, it is silent corruption.

## 3. Refined proposal

My refined design is:

- **Unified prompt**
- **Category inferred from `question` + `ideal_answer`**
- **Category-specific atomic rubric inside the unified prompt**
- **Discrete integer score `0..4`, normalized to `0.0..1.0` in Python**
- **Exactly two output lines**
- **No JSON**
- **No visible analysis**
- **Hard caps for benchmark-critical mistakes**

This keeps the strongest ideas from the other proposals while removing the parts most likely to fail on the actual interface and actual model.

### Scoring model

- `4` = fully correct
- `3` = strong but not perfect
- `2` = partial success
- `1` = weak signal only
- `0` = failure

Normalized score is `raw_score / 4.0`.

### Why this is better

- It keeps Claude's useful bucketed scoring without depending on a missing `category` parameter.
- It keeps Gemini's intuition that the judge should internally compare present vs missing content, but does **not** expose that analysis in the output.
- It explicitly encodes the failure cases this benchmark actually cares about:
  - contradiction tasks: both sides + neutrality matter
  - temporal tasks: final answer correctness matters

### Parsing strategy

Primary parse:

- parse `^SCORE:\s*([0-4])$`
- parse `^JUSTIFICATION:\s*(.+)$`
- normalize with `score / 4.0`

Fallback parse:

- strip code fences if present
- search for the first standalone integer `0` to `4` near a `SCORE` marker
- if still missing, search for a float in `[0, 1]`, convert to nearest bucket, and log malformed output
- if parsing still fails, return `0.0` with a parse-error justification

That parser is strict first and conservative second. It does not silently accept garbage as valid evidence.

## 4. Exact refined prompt text

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

First, determine the task type from the question and ideal answer:
- contradiction_resolution: the ideal answer identifies conflicting claims and asks for clarification or explicitly avoids choosing a side.
- temporal_reasoning: the ideal answer reasons about dates, durations, ordering, deadlines, or elapsed time.

Before scoring, internally compare the generated answer against the ideal answer and identify which required elements are present, missing, or wrong. Do not print this internal analysis.

General rules:
- Judge semantic correctness, not wording overlap.
- Use only the question, ideal answer, and generated answer below.
- Prefer the lower score when uncertain.
- Empty, irrelevant, or content-free answers score 0.
- Fluent wording does not earn credit if the core content is wrong.

Rubric for contradiction_resolution:
- 4: clearly states there is a contradiction or inconsistency, captures both conflicting claims or their substance, and asks for clarification or explicitly refuses to choose a side.
- 3: clearly states there is a contradiction or inconsistency and captures both sides, but the clarification or neutrality step is weaker than ideal.
- 2: identifies inconsistency but omits one side, describes the conflict vaguely, or mixes clarification with premature resolution.
- 1: weak hint of uncertainty or mismatch, but no clear contradiction is framed between two claims.
- 0: misses the contradiction, chooses one side as settled, or is off-topic.

Hard caps for contradiction_resolution:
- If both conflicting sides are not represented, the score cannot exceed 2.
- If the answer chooses one side as settled without clearly flagging a contradiction, the score must be 0.

Rubric for temporal_reasoning:
- 4: correct final temporal conclusion with correct dates, ordering, duration, and units.
- 3: correct final conclusion with one minor missing supporting detail.
- 2: partially correct setup or method, but the final number, ordering, unit, or conclusion is wrong or incomplete.
- 1: mentions relevant dates or time concepts but the reasoning is mostly unsupported or wrong.
- 0: no meaningful temporal reasoning, wrong answer, empty answer, or off-topic.

Hard caps for temporal_reasoning:
- If the final numeric or ordering conclusion is wrong, the score cannot exceed 2.
- If the answer gives no concrete temporal support when the ideal answer depends on dates, durations, or ordering, the score cannot exceed 1.

Question:
{{QUESTION}}

Ideal answer:
{{IDEAL_ANSWER}}

Generated answer:
{{GENERATED_ANSWER}}
```

## 5. Remaining disagreements I want to flag

- **I still reject visible analysis output.** If someone wants `Analysis:` in the response, they are optimizing for interpretability of the judge instead of reliability of the pipeline. That is the wrong trade-off here.
- **I still reject output formats that depend on perfect JSON.** A two-line labeled format is simpler and more robust on Gemma.
- **I reject generous scoring for wrong final temporal answers.** "Correct method, wrong answer" is partial credit, not near-success.
- **I reject any contradiction rubric that gives high credit without both sides present.** If both sides are missing, the scorer is rewarding hand-wavy pattern matching instead of actual contradiction resolution.
- **If someone wants the prompt to consume an explicit category input, that is only acceptable if the function signature changes. With the current code, designing around a missing argument is simply wrong.**

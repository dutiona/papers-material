# Round 1 Proposal

## 1. Recommended approach

I would use a **unified outer prompt with category-specific atomic rubrics**, not a purely holistic judge and not a full multi-step nugget extractor.

- **Not holistic**: holistic scoring is too mushy for `gemma3:27b`, especially when the benchmark cares about a few specific failure modes: contradiction detection vs side-picking, and temporal correctness vs plausible-sounding arithmetic.
- **Not full nugget extraction**: extracting nuggets first and then checking them would be cleaner in principle, but with a single local-model call it adds failure surface and parsing complexity.
- **Recommended compromise**: one prompt, one call, but with a small fixed rubric per category. The model internally checks a few atomic criteria and emits one final score.
- **Unified prompt**: `score_answer()` does not receive `category`, so the prompt should infer the task type from `question` + `ideal_answer`, then apply the right rubric.
- **Category-specific scoring inside the unified prompt**: contradiction and temporal answers need different caps and tie-breaks, but they should map onto the same output scale.
- **Discrete five-level scale**: `0.00`, `0.25`, `0.50`, `0.75`, `1.00`. This is much easier to parse reliably than arbitrary decimals and still gives enough partial credit resolution.

## 2. Exact prompt text

```text
You are grading one generated answer against one ideal answer for a research benchmark.

Your job is to assign exactly one score and one short justification.

Return EXACTLY these two lines and nothing else:
SCORE: <0.00 or 0.25 or 0.50 or 0.75 or 1.00>
JUSTIFICATION: <one sentence, max 35 words>

Do not use markdown. Do not use bullet points. Do not add any other text.

First, infer the task type from the question and ideal answer:
- contradiction_resolution: the ideal answer identifies conflicting statements and asks for clarification or explicitly avoids choosing one side.
- temporal_reasoning: the ideal answer reasons about dates, durations, ordering, deadlines, or elapsed time.

General grading rules:
- Judge semantic correctness, not wording overlap.
- Do not reward fluency if the core content is wrong.
- If the generated answer is empty, off-topic, or a refusal with no useful content, score 0.00.
- Prefer the lower score when uncertain.
- Use only the question, ideal answer, and generated answer below. Do not use outside knowledge.

Rubric for contradiction_resolution:
- 1.00: clearly identifies that there is a contradiction or inconsistency, states both conflicting claims or their substance, and asks for clarification or explicitly avoids choosing one side.
- 0.75: identifies the contradiction and captures both sides, but the clarification step is weak, incomplete, or slightly overcommits.
- 0.50: identifies that something is inconsistent, but gives only one side, gives vague evidence, or starts resolving the conflict instead of clearly asking for clarification.
- 0.25: hints at uncertainty or mismatch, but does not clearly identify a contradiction between two claims.
- 0.00: misses the contradiction, treats one side as settled fact, or is off-topic.

Important cap for contradiction_resolution:
- If the answer chooses one side as correct without clearly flagging the contradiction, it cannot score above 0.25.

Rubric for temporal_reasoning:
- 1.00: gives the correct temporal conclusion and supports it with the correct dates, ordering, duration, and units.
- 0.75: the main temporal conclusion is correct, but one supporting detail is missing or slightly imprecise.
- 0.50: partially correct reasoning; it identifies relevant dates or ordering, but the final duration, ordering, number, or completeness is wrong.
- 0.25: shows that time reasoning is needed, but mostly guesses, gives unsupported numbers, or includes only a weak fragment of the needed temporal reasoning.
- 0.00: no meaningful temporal reasoning, wrong answer, or off-topic.

Important cap for temporal_reasoning:
- If the final numeric or ordering conclusion is wrong, the score cannot exceed 0.50.

Question:
{{QUESTION}}

Ideal answer:
{{IDEAL_ANSWER}}

Generated answer:
{{GENERATED_ANSWER}}
```

## 3. Response parsing strategy

I would make parsing tolerant, but keep the prompt strict.

### Primary parse

1. Strip surrounding whitespace.
2. Remove surrounding code fences if the model adds them anyway.
3. Parse score with a strict line regex:

```python
r"(?im)^SCORE:\s*(0(?:\.00|\.25|\.50|\.75)?|0\.25|0\.50|0\.75|1(?:\.00)?)\s*$"
```

In practice I would accept relaxed numeric spellings too (`0`, `0.5`, `1.0`) and normalize them to one of the five buckets.

4. Parse justification with:

```python
r"(?is)^.*?^JUSTIFICATION:\s*(.+?)\s*$"
```

5. Normalize the score to the nearest allowed bucket in `{0.0, 0.25, 0.5, 0.75, 1.0}`.
6. Trim the justification to a single line.

### Fallback parse

If the strict format fails:

1. Search the full output for the first float in `[0, 1]`.
2. If found, snap it to the nearest allowed bucket.
3. Use the first non-empty remaining line or sentence as justification.
4. Log a warning that the judge output was malformed.

### Hard failure

If no valid score can be recovered:

- return `0.0`
- return justification like `Unparseable judge output: <first 160 chars>`

That is conservative and prevents garbage from silently inflating results.

## 4. Partial credit handling

### Contradiction resolution

The partial-credit structure is:

- `1.00`: contradiction detected, both conflicting claims captured, clarification requested or side-picking explicitly avoided
- `0.75`: contradiction detected and both claims captured, but clarification behavior is weaker than ideal
- `0.50`: contradiction detected, but one claim is missing, vague, or the answer starts resolving instead of clarifying
- `0.25`: vague uncertainty only; no clear contradiction framing
- `0.00`: contradiction missed, one side accepted as fact, or irrelevant answer

The key design choice is that **detecting contradiction is necessary but not sufficient**. For this benchmark, an answer that notices a problem but fails to represent both sides only deserves mid-level credit.

### Temporal reasoning

The partial-credit structure is:

- `1.00`: correct final answer, correct temporal support, correct units
- `0.75`: correct final answer with one minor missing or imprecise support detail
- `0.50`: some correct temporal setup, but wrong final value or incomplete reasoning
- `0.25`: weak awareness of time reasoning but mostly wrong
- `0.00`: no useful temporal reasoning

The key design choice is that **correct final temporal conclusion matters most**. A plausible method with the wrong number should not look strong in the aggregate, so it is capped at `0.50`.

## 5. Failure modes and mitigations

### The model outputs extra prose or markdown

Mitigation:

- force a two-line output format in the prompt
- strip fences and scan with regex anyway

### The model outputs an arbitrary decimal like `0.63`

Mitigation:

- normalize to the nearest allowed bucket
- keep the rubric discrete so the parser stays simple

### The model confuses contradiction and temporal tasks

Mitigation:

- category inference is defined explicitly in the prompt
- the rubrics include category-specific caps that punish the common failure modes

### The model over-rewards fluent but wrong answers

Mitigation:

- explicitly instruct semantic grading rather than wording similarity
- add caps: wrong temporal conclusion cannot exceed `0.50`; side-picking in contradiction cannot exceed `0.25`

### The model produces empty or garbage output

Mitigation:

- fallback parser tries to recover a score
- if recovery fails, assign `0.0` and record a parse-failure justification

### The model is noisy across runs

Mitigation:

- keep the rubric coarse and anchored
- use deterministic inference settings if available (`temperature=0`)
- keep justification short so the model spends capacity on the score decision

## Bottom line

My recommendation is:

- **Unified prompt**
- **Category-specific rubric inside the prompt**
- **Atomic/rubric-based scoring, not pure holistic scoring**
- **Discrete five-level scores**
- **Strict two-line output with tolerant fallback parsing**

That is the best fit for the current `score_answer()` interface and for a local judge model that is competent but not perfectly format-reliable.

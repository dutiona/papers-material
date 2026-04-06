# Round 2 — Claude (Opus 4.6)

## Agreements

### From Codex

- **Two-line format over JSON**: Codex is right. JSON is fragile on local models — one missing quote breaks parsing. `SCORE: 0.75` / `JUSTIFICATION: ...` is more robust. I'm switching.
- **Discrete 5-level scale**: Codex's `{0.00, 0.25, 0.50, 0.75, 1.00}` is functionally identical to my 0-4 scale but already on the right range. Simpler. I'm adopting this.
- **Explicit caps in the prompt**: This is Codex's strongest idea. Writing "If the answer picks a side without flagging contradiction, score cannot exceed 0.25" directly in the prompt is better than hoping the rubric implies it. It becomes a hard rule the model can check.
- **Category inference**: Codex is right that the current `score_answer()` signature lacks a `category` parameter. The question is whether to add one (clean) or infer (fragile). I think we should **add the parameter** rather than asking a 27b model to infer task type.

### From Gemini

- **Analysis step (chain-of-thought)**: Gemini's `Analysis:` step before `Score:` is valuable. Making the model enumerate what's present/missing before scoring forces grounding. This reduces hallucinated scores. I'm incorporating this.
- **Category-specific integrity rules in the prompt**: Good framing. "For Contradictions: MUST detect, cite BOTH, remain neutral" is clear.

## Disagreements

### With Codex

- **Category inference from question text**: This is fragile. The model has to first identify the task type, then apply the right rubric. If it misidentifies (and 27b models will), it applies the wrong rubric. Just pass the category. The function signature should change.
- **35-word justification limit**: Too restrictive. Some scoring decisions genuinely need 2 sentences. Drop the word limit.

### With Gemini

- **Continuous 0.0-1.0 scale**: This is the biggest disagreement. Gemma3 27b will output arbitrary values like 0.63, 0.87, 0.42. These look precise but are noise. A 5-point discrete scale (Codex's approach) is more reliable AND more meaningful. There's no difference between 0.63 and 0.67 that the model can justify.
- **No explicit score caps**: Gemini's rubric says "Detects the core issue but fails execution = 0.5" but doesn't enforce it as a hard rule. A model that generates fluent text about contradictions will get pulled toward higher scores unless you explicitly cap it.
- **Three-section format adds a parsing target**: `Analysis:` / `Justification:` / `Score:` is three things to parse. More surface area for failure. I'd keep Analysis as a thinking step but only require two parseable outputs.

## Refined Proposal

Key changes from Round 1:

1. Switch to two-line format (from Codex)
2. Add Analysis thinking step (from Gemini) but don't parse it — it's for the model's benefit
3. Explicit score caps (from Codex)
4. Discrete 5-level scale (from Codex)
5. **Add `category` parameter to `score_answer()`** instead of inferring

### Refined Prompt

```
You are evaluating a generated answer against an ideal answer for a memory benchmark.

CATEGORY: {category}
QUESTION: {question}
IDEAL ANSWER: {ideal_answer}
GENERATED ANSWER: {generated_answer}

First, think step by step: which key facts from the ideal answer appear in the generated answer? Which are missing or wrong?

Then output EXACTLY two lines:
SCORE: <one of: 0.00, 0.25, 0.50, 0.75, 1.00>
JUSTIFICATION: <one or two sentences explaining the score>

Scoring rules for contradiction_resolution:
- 1.00: identifies the contradiction, states both conflicting claims, asks for clarification or stays neutral
- 0.75: identifies the contradiction and both claims, but clarification is weak or slightly overcommits
- 0.50: identifies inconsistency but gives only one side, or starts resolving instead of clarifying
- 0.25: hints at uncertainty without clearly identifying a contradiction
- 0.00: misses the contradiction, picks a side as fact, or is off-topic/empty
HARD CAP: if the answer picks one side as correct without flagging the contradiction, score CANNOT exceed 0.25.

Scoring rules for temporal_reasoning:
- 1.00: correct answer with correct dates, duration, units, and calculation
- 0.75: correct conclusion but one minor detail missing or imprecise
- 0.50: relevant dates identified but final calculation, duration, or ordering is wrong
- 0.25: attempts temporal reasoning but with wrong dates or unsupported numbers
- 0.00: no temporal reasoning, completely wrong, or off-topic/empty
HARD CAP: if the final numeric or ordering conclusion is wrong, score CANNOT exceed 0.50.

If the generated answer is empty, return SCORE: 0.00.
Do not output anything except the two lines above.
```

### Parsing

Same as Codex's: regex for `SCORE:` line, snap to nearest bucket, regex for `JUSTIFICATION:` line, fallback to first float found, hard failure returns `(0.0, "PARSE_ERROR: ...")`.

## Remaining Disagreement

**Category parameter vs inference**: I strongly believe we should add `category: QuestionCategory` to `score_answer()`. The caller already knows the category. Making the judge infer it is unnecessary fragility. Codex disagrees — they prefer the current signature. I'd rather change the interface than make every scoring call depend on correct category inference by a 27b model.

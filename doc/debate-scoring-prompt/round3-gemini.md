# Round 3: Final Resolution

## 1. ANALYSIS STEP: Visible "Analysis:" Section
**Position**: Visible.
**Strongest Argument**: For 27b models, the "score" token is a prediction based on the preceding context; forcing a visible "Analysis" block ensures that the evidence for the score is explicitly generated before the model picks a number. This "computational trace" acts as a grounding anchor that significantly reduces over-generous scoring and prevents the model from ignoring missing nuggets in favor of fluency. It provides a human-readable audit trail that justifies the score, making the entire evaluation process more transparent.

## 2. CATEGORY PARAMETER: Explicitly Passed
**Position**: Explicit.
**Strongest Argument**: Since `QuestionCategory` is already a fundamental part of the BEAM dataset and the experiment’s data types, failing to pass it to the scorer creates an artificial and unnecessary failure point for the LLM. Explicitly passing the category guarantees 100% task-inference reliability, allowing the prompt to focus entirely on rigorous grading rather than classification logic. This trivial API change simplifies the prompt, improves speed, and ensures the correct "Hard Caps" are applied to the correct task every time.

---

## FINAL Complete Prompt Text

```text
### Role
You are a precise academic evaluator for a memory-system benchmark. Compare the "Generated Answer" against the gold-standard "Ideal Answer."

### Context
CATEGORY: {category}
QUESTION: {question}
IDEAL ANSWER: {ideal_answer}
GENERATED ANSWER: {generated_answer}

### Instructions
1. ANALYSIS: Briefly list which specific facts or requirements from the Ideal Answer are present in the Generated Answer.
2. JUSTIFICATION: Provide a 1-sentence explanation for the score.
3. SCORE: Assign exactly one integer (0, 1, 2, 3, or 4) based on the rubric for the {category} task below.

### Rubric for CONTRADICTION RESOLUTION
- 4: Perfect. Identifies the contradiction, cites BOTH conflicting sides, and remains neutral (asks for clarification).
- 3: Good. Identifies the contradiction and both sides, but fails to remain neutral (picks a side).
- 2: Fair. Mentions that an inconsistency exists, but only cites one side or is vague about the specifics.
- 1: Poor. Acknowledges a problem but treats one side as factually correct without flagging the conflict.
- 0: Failure. Misses the contradiction entirely or provides irrelevant information.
**CRITICAL CAP**: If the Generated Answer chooses one side as "correct" without explicitly flagging the existence of a contradiction, the MAX score is 1.

### Rubric for TEMPORAL REASONING
- 4: Perfect. Provides the correct final numeric, ordering, or duration conclusion with correct supporting logic.
- 3: Good. Correct final conclusion, but misses one supporting date or uses slightly imprecise units.
- 2: Fair. Correct logic/method, but makes a calculation error (wrong final number).
- 1: Poor. Shows awareness of time reasoning but provides wrong dates or nonsensical logic.
- 0: Failure. No temporal reasoning attempted or completely wrong answer.
**CRITICAL CAP**: If the final numeric, ordering, or duration conclusion is wrong, the MAX score is 2.

### Output Format
Analysis: <your_analysis>
Justification: <your_justification>
Score: <0, 1, 2, 3, or 4>
```

# Round 2: Critique and Refined Proposal

## 1. Critique of Other Proposals

### Claude (Opus 4.6)
*   **Agreement**: I agree with the **0-4 integer scale**. It is significantly more stable for local models than continuous floats.
*   **Disagreement**: I strongly disagree with the **JSON output format**. Local models like `gemma3:27b` often fail to close brackets or include illegal characters when run via Ollama. Key-Value pairs are much more resilient.
*   **Disagreement**: Claude's rubric is too "soft." It lacks the hard constraints needed to punish "side-picking" in contradictions, which is a primary failure mode this experiment aims to measure.

### Codex
*   **Agreement**: I agree with the **Hard Caps/Hard Constraints**. Capping a "side-picked" answer at a low score regardless of fluency is the only way to get a clean signal for the BEAM project.
*   **Agreement**: I agree with the **Key-Value format** and the logic for **Category Inference** within the prompt.
*   **Disagreement**: I disagree with the **0.25/0.50/0.75 float buckets**. While parseable, they are less "natural" for an LLM's next-token prediction than a simple 0-4 integer.
*   **Disagreement**: Codex jumps straight to the score. For a 27b model, an explicit **Analysis step** (mapping nuggets) acts as a necessary anchor to prevent "hallucinated correctness."

## 2. Refined Proposal: The "Capped Analysis" Prompt

I propose a **Unified Key-Value Prompt** that utilizes **Chain-of-Thought Analysis** followed by a **Capped Integer Score**.

### The Refined Prompt
```text
### Role
You are a precise academic grader for a memory-system benchmark. Your task is to compare a "Generated Answer" against a gold-standard "Ideal Answer."

### Context
Question: {question}
Ideal Answer: {ideal_answer}
Generated Answer: {generated_answer}

### Instructions
1. IDENTIFY TASK: Determine if this is a "Contradiction Resolution" or "Temporal Reasoning" task.
2. ANALYSIS: Briefly list which specific facts or requirements from the Ideal Answer are present in the Generated Answer.
3. JUSTIFICATION: Provide a 1-sentence explanation for the score.
4. SCORE: Assign exactly one integer (0, 1, 2, 3, or 4) based on the rubrics below.

### Rubric for CONTRADICTION RESOLUTION
- 4: Perfect. Identifies the contradiction, cites BOTH conflicting sides, and remains neutral (asks for clarification).
- 3: Good. Identifies the contradiction and cites both sides, but fails to ask for clarification.
- 2: Partial. Identifies that "something is wrong," but only cites one side or is vague.
- 1: Poor. Mentions the topic but chooses one side as factually correct without flagging the conflict.
- 0: Failure. Misses the contradiction entirely or provides irrelevant info.
**SCORING CAP**: If the answer chooses one side as "correct" without explicitly flagging the contradiction, the MAX score is 1.

### Rubric for TEMPORAL REASONING
- 4: Perfect. Correct final numeric/date conclusion with correct supporting math/logic.
- 3: Good. Correct final conclusion, but misses one supporting date or uses wrong units.
- 2: Fair. Correct logic/method, but makes a calculation error (wrong final number).
- 1: Poor. Shows awareness of time but provides wrong dates or nonsensical logic.
- 0: Failure. No temporal reasoning or completely wrong answer.
**SCORING CAP**: If the final numeric, ordering, or duration conclusion is wrong, the MAX score is 2.

### Output Format
Analysis: <your_brief_analysis>
Justification: <your_justification>
Score: <0, 1, 2, 3, or 4>
```

## 3. Response Parsing & Normalization

1.  **Regex**: Use `Score:\s*(\d)` to extract the integer.
2.  **Normalization**: Map the integer to the 0.0-1.0 scale required by `TrialResult`:
    *   `4` -> `1.0`
    *   `3` -> `0.75`
    *   `2` -> `0.5`
    *   `1` -> `0.25`
    *   `0` -> `0.0`
3.  **Fallback**: If no score is found, return `0.0` with a "PARSE_ERROR" justification. This prevents "failing upward."

## 4. Remaining Disagreements to Flag
*   **Scale Resolution**: Codex argues for a 5-bucket float scale. I argue that 0-4 integers are mentally easier for the LLM to ground against the rubric categories.
*   **Thinking Step**: I insist on the `Analysis:` step. Without it, local models often ignore the "both sides" requirement for contradictions because they don't "look" for them until they've already started writing the justification.

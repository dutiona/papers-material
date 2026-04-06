# Round 1 Proposal: Semi-Structured Holistic Scoring for Gemma 3

## 1. Recommended Approach: Unified Semi-Structured Holistic
I recommend a **Unified Semi-Structured Holistic** approach. 

*   **Unified**: Using the same prompt for both categories ensures that the "scale" of success is calibrated identically. Since the `ideal_answer` already encodes the specific category requirements (e.g., identifying both sides of a contradiction), a unified prompt that prioritizes "fidelity to the ideal answer" is more robust than maintaining two separate rubrics.
*   **Semi-Structured**: While pure nugget extraction is mathematically elegant, local models like Gemma 3 27b often struggle with the overhead of multi-step extraction and counting in a single call. Instead, I use a "Thinking Step" (Analysis) where the model identifies correct vs. missing nuggets *before* outputting the score. This stabilizes the final score.

## 2. EXACT Prompt Text
This prompt is designed to be used in the `messages` array of the `ollama.chat` call within `score_answer()`.

```text
### System Role
You are a rigorous academic evaluator for AI agent experiments. Your goal is to score a "Generated Answer" based on its alignment with a "Ideal Answer" (the ground truth).

### Context
Question: {question}
Ideal Answer: {ideal_answer}
Generated Answer: {generated_answer}

### Evaluation Criteria
1. Accuracy: Does the Generated Answer contain the core factual "nuggets" found in the Ideal Answer?
2. Category-Specific Integrity:
   - For Contradictions: The answer MUST detect the inconsistency, cite BOTH conflicting facts, and remain neutral (ask for clarification). Identifying only one side or picking a "winner" is a significant failure.
   - For Temporal Reasoning: Dates, durations, and calculations must be exact. Methodological correctness with a calculation error receives partial credit.

### Scoring Rubric (0.0 to 1.0)
- 1.0 (Excellent): Perfect alignment. Detects contradiction (both sides + neutral) or performs perfect temporal math.
- 0.75 (Good): Core logic is correct; minor phrasing issues or one non-critical detail missing.
- 0.5 (Fair): Partial success. Detects the core issue (e.g., "there is a contradiction") but fails the execution (e.g., picks a side) OR correct temporal method but wrong final number.
- 0.25 (Poor): Mentions relevant entities or dates but fails to address the actual question/contradiction.
- 0.0 (Failure): Completely incorrect, irrelevant, or empty.

### Instructions
1. ANALYSIS: Briefly list which nuggets from the Ideal Answer are present and which are missing/wrong in the Generated Answer.
2. JUSTIFICATION: Provide a 1-2 sentence explanation for the score.
3. SCORE: Provide the final float score (0.0 to 1.0).

### Output Format
Analysis: <your_analysis>
Justification: <your_justification>
Score: <float_score>
```

## 3. Response Parsing Strategy
To ensure reliability with a local LLM, I will use a robust multi-line parsing strategy:

1.  **Regex for Score**: Use `Score:\s*([0-1](?:\.\d+)?)` to find the numerical value. This handles variations like "Score: 0.5" or "Score: .5".
2.  **Justification Extraction**: Extract the text between the `Justification:` and `Score:` markers.
3.  **Fallback**: If the regex fails, attempt to find any float in the last two lines of the output. If still failing, return `(0.0, "Error: Could not parse LLM output.")`.

## 4. Handling Partial Credit
The rubric explicitly defines the "0.5" and "0.75" tiers to handle the specific requirements of the BEAM experiment:

*   **Contradiction Resolution**:
    *   **0.5**: The model says "You said X and Y, which is confusing" (Identifies contradiction, cites both sides, but fails to ask for clarification) OR identifies the contradiction but picks a side.
    *   **0.75**: Identifies contradiction, cites both sides, asks for clarification, but misses a specific date or name mentioned in the ideal answer.
*   **Temporal Reasoning**:
    *   **0.5**: "The time between Jan 1 and Feb 1 is 5 weeks" (Method is correct—subtracting dates—but math is wrong).
    *   **0.75**: Correct duration but wrong unit (e.g., "30 days" instead of "1 month") or correct math but missing one of the anchor dates.

## 5. Failure Modes and Mitigations
*   **Failure**: LLM outputs a range (e.g., "Score: 0.7-0.8").
    *   **Mitigation**: The regex `([0-1](?:\.\d+)?)` will capture the first number (0.7).
*   **Failure**: LLM writes a long preamble before the markers.
    *   **Mitigation**: The marker-based approach (`Analysis:`, `Justification:`, `Score:`) ignores any text before the first marker.
*   **Failure**: LLM hallucinates facts not in the Ideal Answer to justify a score.
    *   **Mitigation**: The "Analysis" step forces the LLM to explicitly map the Generated Answer nuggets back to the Ideal Answer nuggets *before* scoring, which reduces grounding errors.
*   **Failure**: Empty or "I don't know" responses from the judge.
    *   **Mitigation**: The `score_answer` function should wrap the Ollama call in a try/except block and return `0.0` for any timeouts or API errors.

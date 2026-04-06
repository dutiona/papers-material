# Debate Briefing: score_answer() Prompt Design

## Context

We're building a BEAM typed-routing pilot experiment for a position paper ("The Missing Knowledge Layer in Cognitive Architectures for AI Agents"). The experiment tests whether routing queries to typed memory stores (knowledge-base with supersession vs memory-engine with bi-temporal) improves contradiction-resolution and temporal-reasoning scores vs a flat baseline.

## The Function to Design

`src/evaluation/llm.py :: score_answer(question, ideal_answer, generated_answer, model) -> (float, str)`

This function uses a LOCAL LLM (gemma3 27b via Ollama) to judge how well a generated answer matches the BEAM-provided ideal answer. Returns a score (0.0-1.0) and justification string.

## Two Question Categories

### Contradiction Resolution (40 questions)

- Tests: did the system detect contradictory statements in the conversation?
- Ideal answers typically: identify both conflicting statements, ask for clarification
- Example ideal: "I notice you've mentioned contradictory information. You said you have never written any Flask routes, but you also mentioned implementing a basic homepage route with Flask. Could you clarify?"
- What matters: detecting the contradiction, citing both sides, NOT picking one

### Temporal Reasoning (40 questions)

- Tests: can the system reason about time durations, ordering, deadlines?
- Ideal answers typically: calculate correct durations, reference specific dates
- Example ideal: "There are exactly 4 weeks between finishing transaction management features on January 15, 2024, and the final deployment deadline on March 15, 2024."
- What matters: correct calculation, correct dates, correct units

## Constraints

1. Single LLM call per question (budget: ~940K tokens total, local model)
2. Must return parseable float score + string justification
3. The prompt runs on gemma3 27b — not frontier-level instruction following
4. Score must be comparable across categories (0.5 on contradiction ≈ 0.5 on temporal)
5. Must handle edge cases: empty answers, off-topic answers, partially correct

## Design Questions

1. Should scoring be holistic (one prompt, one score) or nugget-based (extract atomic facts, check each)?
2. Should contradiction and temporal questions use the same prompt or category-specific prompts?
3. What rubric/scale should the prompt use? (binary 0/1? 4-point? continuous?)
4. How to ensure the local model outputs parseable scores reliably?
5. How to handle partial credit? (detected contradiction but wrong resolution; correct method but wrong number)

## Key Files to Read

- `src/evaluation/llm.py` — the function stub with docstring
- `src/evaluation/types.py` — TrialResult, ExperimentReport (how scores are consumed)
- `src/dataset/types.py` — ProbingQuestion structure
- `doc/PROMPT.md` — full experiment design

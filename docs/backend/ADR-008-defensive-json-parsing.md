# ADR-008: Defensive JSON Parsing with Regex Fallback for LLM Outputs

**Status:** Accepted <br>
**Date:** 2026-02-10 <br>
**Deciders:** vanillasky <br>

## Context

Every agent (Curriculum, Skill, Action, Critic) asks the LLM to return structured JSON and then parses the response. LLMs do not reliably return valid, parseable JSON even when instructed to. Common failure modes observed during development:

1. **Markdown code fences** — the model wraps JSON in ` ```json ... ``` ` despite instructions not to.
2. **Trailing commas** — JSON is invalid but the model includes them.
3. **Extra prose** — the model adds a sentence before or after the JSON object.
4. **Nested explanation** — the model returns `{"plan": [...], "explanation": "Here is my reasoning..."}` when only `[...]` was requested.
5. **Single-quoted keys** — Python dict syntax, not valid JSON.
6. **Partial output** — the model truncates mid-JSON (rare but catastrophic if not handled).

Using `response_format={"type": "json_object"}` (OpenAI's structured output mode) eliminates most issues but:
- Requires schema-compatible models (GPT-4o+, not all fine-tunes).
- Does not work with Ollama models.
- Returns the entire response as one JSON object, conflicting with agents that expect a bare array `[...]`.

The system must handle all failure modes gracefully, with a defined fallback for each agent.

## Decision

All agents inherit from `BaseAgent`, which implements a **two-stage parsing pipeline** in `_parse_json_response()`:

### Stage 1: Direct JSON parse

```python
try:
    return json.loads(response.strip())
except json.JSONDecodeError:
    pass  # fall through to Stage 2
```

If the LLM returned clean JSON, this succeeds immediately at zero cost.

### Stage 2: Regex extraction

Three patterns are tried in order:

```python
# Pattern A: JSON array (for Action agent output)
match = re.search(r'\[[\s\S]*\]', response)

# Pattern B: JSON object (for Curriculum, Critic, Skill output)  
match = re.search(r'\{[\s\S]*\}', response)

# Pattern C: Fenced code block (```json ... ``` or ``` ... ```)
match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
```

The extracted substring is passed to `json.loads()`. If all three patterns fail, the method raises a `ValueError` with the raw response attached for debugging.

### Stage 3: Retry with error injection

If parsing fails, `BaseAgent` re-calls the LLM with an error message appended to the user message:

```python
retry_message = (
    f"{original_message}\n\n"
    f"[PARSE ERROR] Your previous response could not be parsed as JSON.\n"
    f"Raw response: {raw_response[:200]}...\n"
    f"Please return ONLY valid JSON with no markdown, no explanation."
)
```

Up to **3 retries** per agent call. After 3 failures, the agent raises, which the LangGraph node catches and routes to a safe fallback (e.g., CurriculumAgent returns the default task `"Set up the assembly plate on Preparation1"`).

### Agent-specific defaults on parse failure

| Agent | Fallback on parse failure |
|-------|--------------------------|
| CurriculumAgent | `{"task": "Set up the assembly plate on Preparation1", "reasoning": "parse error fallback", "difficulty": 1}` |
| ActionAgent | Returns empty plan `[]` (Critic will judge as failure, triggering retry) |
| CriticAgent | `{"success": False, "reasoning": "parse error", "feedback": "retry"}` |
| SkillAgent | Logs error, skips learning (non-fatal; skill library simply doesn't grow) |

## Consequences

**Positive:**
- The system degrades gracefully rather than crashing on LLM formatting inconsistencies.
- Three retries with error feedback substantially increase the parse success rate without requiring `json_object` mode.
- Agent-specific fallbacks ensure the LangGraph loop continues even on repeated parse failures.

**Negative / trade-offs:**
- Up to 3 extra LLM calls per parse failure, adding latency and cost.
- Regex extraction can succeed on malformed JSON substrings that then fail `json.loads()` — the error message in that case is confusing.
- The fallback for ActionAgent (empty plan) means a parse failure looks like a failed execution to the Critic — two different failure modes produce the same observable output.

## Alternatives Considered

### A. Use OpenAI `response_format={"type": "json_object"}`
**Partially adopted.** The `generate_structured()` method on `BaseLLMClient` uses this path. However, agents use `generate_response()` + manual parsing because: (a) Ollama compatibility, (b) some agents expect bare arrays which `json_object` cannot produce, (c) the structured path requires a JSON Schema up front and agents evolved faster than their schemas.

### B. Instructor / Outlines (constrained decoding)
**Considered.** Libraries like `instructor` wrap the OpenAI client to enforce Pydantic model output. Rejected because: (a) adds a dependency, (b) no Ollama support, (c) constrained decoding on Ollama requires model-specific grammar files.

### C. Pydantic `.model_validate_json()` directly on raw response
**Rejected as primary strategy.** Pydantic cannot handle prose-wrapped JSON or code fences. It does validate the parsed structure once regex extraction succeeds.

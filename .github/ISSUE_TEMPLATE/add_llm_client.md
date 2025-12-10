---
name: "Feature: Add New LLM Client"
about: Implement a new LLMClient based on BaseLLMClient abstraction
title: "[LLM] Add new provider client"
labels: [enhancement, LLM, good first issue]
---

## Summary

Implement a new LLM client class that inherits from `BaseLLMClient` and provides full support for a new model provider.

## Requirements

- [ ] New class implements all required abstract methods in `BaseLLMClient`
- [ ] Provider configuration flag added (env/settings)
- [ ] Includes basic integration test in `tests/llm/`
- [ ] Error handling & logging included
- [ ] Follows code style (PEP8 + type hints)
- [ ] No mutation of input arguments (immutability principle)
- [ ] No hidden side effects

## Implementation Path

1. Create file at: `app/llm/<provider>_client.py`
2. Use async `httpx` or local transport as needed
3. Wire into existing LLM factory / settings selector
4. Add minimal docs: usage example + needed environment variables

## Notes for Assignee

- If external API: add safe mock testing
- Run CI before pushing:
  ```bash
  uv run pytest
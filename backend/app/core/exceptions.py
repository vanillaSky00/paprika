"""Domain-specific exceptions for the Paprika backend.

Keep this hierarchy small. Each subclass marks a distinct failure boundary
that callers handle differently (e.g. client-visible message vs. retry vs.
fatal). Don't add a subclass unless you actually branch on it.
"""
from __future__ import annotations


class PaprikaError(Exception):
    """Base class for all application errors."""


class InvalidPerceptionError(PaprikaError):
    """Incoming perception payload failed schema validation."""


class ContextBuildError(PaprikaError):
    """PerceptionRenderer failed to build the affordance block."""


class AgentExecutionError(PaprikaError):
    """LangGraph agent invocation raised an error."""

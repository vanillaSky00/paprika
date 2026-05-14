from __future__ import annotations


class PaprikaError(Exception):
    """Base class for all application errors."""


class InvalidPerceptionError(PaprikaError):
    """Incoming perception payload failed schema validation."""


class ContextBuildError(PaprikaError):
    """PerceptionRenderer failed to build the affordance block."""


class AgentExecutionError(PaprikaError):
    """LangGraph agent invocation raised an error."""


class DatabaseError(PaprikaError):
    """Base class for database-layer failures."""


class DatabaseUnavailableError(DatabaseError):
    """Database did not respond to a connectivity probe."""


class PgvectorExtensionError(DatabaseError):
    """Failed to ensure the pgvector extension is installed."""


class MigrationError(DatabaseError):
    """Alembic schema upgrade failed."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4.1-mini"

    # API keys and connection urls
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None

    # LangSmith / LangChain Config
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str = "paprika-agent"

    OPENWEATHER_BASE_URL: str = "http://api.openweathermap.org/data/2.5"
    OPENWEATHER_API_KEY: str | None = None

    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    DATABASE_URL: str = "postgresql+asyncpg://admin:password@localhost:5432/paprika_ai"
    
    model_config = SettingsConfigDict(
        env_file=".env",  # tell Pydantic where to load env variables from
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()

# Export to System Environment
# This ensures LangChain's library code can see the variables
if settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2).lower()
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

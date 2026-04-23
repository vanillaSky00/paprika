import os
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseModel):
    level: str = "INFO"
    file_path: str | None = None
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5


class Settings(BaseSettings):
    REDIS_URL: str ="redis://redis:6379/0"
    
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4.1-mini"

    # API keys and connection urls
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str | None = "gpt-4.1-mini"

    OLLAMA_BASE_URL: str | None = None
    OLLAMA_API_KEY: str | None = None
    OLLAMA_MODEL: str | None = None

    # LangSmith / LangChain Config
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str = "paprika-agent"

    OPENWEATHER_BASE_URL: str = "http://api.openweathermap.org/data/2.5"
    OPENWEATHER_API_KEY: str | None = None

    DATABASE_URL: str = "postgresql+asyncpg://admin:password@localhost:5432/paprika_ai"

    debug: bool = False
    log: LoggingSettings = LoggingSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    
settings = Settings()

# Export to System Environment
# This ensures LangChain's library code can see the variables
if settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2).lower()
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    
    

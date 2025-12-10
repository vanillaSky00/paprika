import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4.1-mini"
    
    # API keys and connection urls
    OPENAI_API_KEY: str | None = None
    
    OLLAMA_BASE_URL: str
    OLLAMA_API_KEY: str | None = None
    OLLAMA_MODEL: str | None = None
    # LangSmith / LangChain Config
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str = "paprika-agent"

    model_config = SettingsConfigDict(
        env_file=".env", # tell Pydantic where to load env variables from
        extra="ignore",
    ) 

settings = Settings()

# Export to System Environment 
# This ensures LangChain's library code can see the variables
if settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2).lower()
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

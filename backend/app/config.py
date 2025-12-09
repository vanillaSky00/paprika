from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4.1-mini"
    
    # API keys and connection urls
    OPENAI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    class Config:
        env_file = ".env" # tell Pydantic where to load env variables from
        
settings = Settings()
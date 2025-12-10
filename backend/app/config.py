from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "gemma3:1b"
    
    # API keys and connection urls
    # openai
    OPENAI_API_KEY: str | None = None
    # ollama
    OLLAMA_API_KEY: str | None = None
    OLLAMA_BASE_URL: str
    

    model_config = SettingsConfigDict(env_file=".env") # tell Pydantic where to load env variables from
        
settings = Settings()
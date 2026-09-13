"""Central configuration. Switch models without code changes via env vars."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite:///./lenny.db"

    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "qwen2.5:3b"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT_S: int = 300

    LLM_FALLBACK_ENABLED: bool = False
    LLM_FALLBACK_PROVIDER: str = "anthropic"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    RETRIEVAL_TOP_K: int = 5
    DATA_DIR: str = "./data/transcripts"
    INDEX_PATH: str = "./data/index/chunks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()

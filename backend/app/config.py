"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mock_llm: bool = True
    llm_backend: str = "mock"  # "mock" | "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:0.6b"
    ollama_timeout_s: float = 120.0

    default_num_candidates: int = 5
    z3_timeout_ms: int = 5000

    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    log_level: str = "INFO"


settings = Settings()

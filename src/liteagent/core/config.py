import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Search in current directory, then in ~/.liteagent/.env
    model_config = SettingsConfigDict(
        env_file=[".env", str(Path.home() / ".liteagent" / ".env")],
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # LLM Providers
    nvidia_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    
    # Default Provider
    default_provider: str = "ollama"
    default_model: str = "llama3" # Default for Ollama

    # Session logging
    log_enabled: bool = True
    log_verbose_raw: bool = True
    log_dir: str = str(Path.home() / ".liteagent")
    log_max_payload_chars: int = 500000
    session_dir: str = str(Path.home() / ".liteagent" / "sessions")

    # Tool inspector server
    inspector_enabled: bool = True
    inspector_host: str = "127.0.0.1"
    inspector_port: int = 8000
    inspector_port_search_limit: int = 100

    # Insight settings
    insight_embedding_provider: str = "gemini"
    insight_embedding_model: Optional[str] = None
    insight_embedding_base_url: str = "http://localhost:11434"
    insight_auto_index: bool = True
    insight_log_discovery: bool = True
    insight_log_paths: list[str] = []

settings = Settings()

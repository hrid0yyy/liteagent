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

settings = Settings()

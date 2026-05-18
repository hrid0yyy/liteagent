import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

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

    # Code Review Graph - Knowledge Base Settings
    crg_enabled: bool = False                    # Enable knowledge base feature
    crg_auto_build: bool = True                  # Build graph on session start if not exists
    crg_check_hash_before_turn: bool = True      # Check hash before each agent turn
    crg_update_async: bool = True                # Update without blocking agent
    crg_wiki_dir: str = ".code-review-graph/wiki"  # Wiki output directory
    crg_context_max_chars: int = 50000           # Max characters for KB context
    crg_include_sections: List[str] = [          # Which wiki sections to include
        "architecture",
        "communities", 
        "hubs",
        "bridges",
        "flows"
    ]

    # Summarizer Node Settings
    summarizer_enabled: bool = True
    summarizer_provider: str = "openrouter"
    summarizer_model: str = "openai/gpt-oss-120b:free"
    summarizer_threshold: int = 4000
    summarize_tools: List[str] = [
        "code-review-graph__explore_codebase_tool",
        "code-review-graph__find_code_tool",
        "code-review-graph__review_changes_composite_tool",
        "code-review-graph__query_graph_tool",
        "code-review-graph__refactor_tool"
    ]

    # MCP Settings
    mcp_config_path: str = "mcp_servers.json"

    def get_mcp_servers(self) -> dict:
        import json
        path = Path(self.mcp_config_path)
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                config = json.load(f)
                return config.get("mcpServers", {})
        except Exception as e:
            print(f"Error loading MCP config: {e}")
            return {}

settings = Settings()

"""
Persistent configuration manager for the LogAnalyzer.
Stores log paths and issue descriptions with unique 4-char IDs
in `.liteagent/analyzer_config.json`.
"""
import json
import string
import random
from pathlib import Path
from typing import Dict, Optional


class AnalyzerConfig:
    """Manages persistent log and issue configuration for the LogAnalyzer."""

    def __init__(self, project_dir: Path):
        self._config_dir = project_dir / ".liteagent"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._config_path = self._config_dir / "analyzer_config.json"
        self._data: Dict = self._load()

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> Dict:
        if self._config_path.exists():
            try:
                return json.loads(self._config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                return {"logs": {}, "issues": {}}
        
        # Create a template configuration ONLY if the file literally doesn't exist
        template = {
            "logs": {
                "exmp": "C:/path/to/your/app.log"
            },
            "issues": {
                "bug1": "Sample issue description here."
            }
        }
        self._config_path.write_text(
            json.dumps(template, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return template

    def _save(self) -> None:
        self._config_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── ID generation ────────────────────────────────────────────────

    def _generate_id(self) -> str:
        """Generate a unique 4-character alphanumeric ID."""
        existing = set(self._data.get("logs", {}).keys()) | set(self._data.get("issues", {}).keys())
        for _ in range(1000):
            candidate = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
            if candidate not in existing:
                return candidate
        raise RuntimeError("Could not generate a unique 4-char ID after 1000 attempts.")

    # ── Log operations ───────────────────────────────────────────────

    def add_log(self, file_path: str) -> str:
        """Add a log file path. Returns the assigned ID."""
        new_id = self._generate_id()
        self._data.setdefault("logs", {})[new_id] = file_path
        self._save()
        return new_id

    def remove_log(self, log_id: str) -> bool:
        """Remove a log entry by ID. Returns True if removed."""
        if log_id in self._data.get("logs", {}):
            del self._data["logs"][log_id]
            self._save()
            return True
        return False

    def edit_log(self, log_id: str, new_path: str) -> bool:
        """Update an existing log entry's path. Returns True if updated."""
        if log_id in self._data.get("logs", {}):
            self._data["logs"][log_id] = new_path
            self._save()
            return True
        return False

    def get_logs(self) -> Dict[str, str]:
        """Return all configured logs {id: path}."""
        return dict(self._data.get("logs", {}))

    # ── Issue operations ─────────────────────────────────────────────

    def add_issue(self, description: str) -> str:
        """Add an issue description. Returns the assigned ID."""
        new_id = self._generate_id()
        self._data.setdefault("issues", {})[new_id] = description
        self._save()
        return new_id

    def remove_issue(self, issue_id: str) -> bool:
        """Remove an issue entry by ID. Returns True if removed."""
        if issue_id in self._data.get("issues", {}):
            del self._data["issues"][issue_id]
            self._save()
            return True
        return False

    def edit_issue(self, issue_id: str, new_description: str) -> bool:
        """Update an existing issue entry's description. Returns True if updated."""
        if issue_id in self._data.get("issues", {}):
            self._data["issues"][issue_id] = new_description
            self._save()
            return True
        return False

    def get_issues(self) -> Dict[str, str]:
        """Return all configured issues {id: description}."""
        return dict(self._data.get("issues", {}))

    # ── Cross-cutting ────────────────────────────────────────────────

    def rename_id(self, old_id: str, new_id: str) -> tuple[bool, str]:
        """
        Rename an existing ID (log or issue) to a new one.
        Returns (success, message).
        """
        if len(new_id) != 4:
            return False, "New ID must be exactly 4 characters."

        all_ids = set(self._data.get("logs", {}).keys()) | set(self._data.get("issues", {}).keys())
        if new_id in all_ids:
            return False, f"ID '{new_id}' is already in use."

        if old_id in self._data.get("logs", {}):
            self._data["logs"][new_id] = self._data["logs"].pop(old_id)
            self._save()
            return True, f"Renamed log '{old_id}' → '{new_id}'."

        if old_id in self._data.get("issues", {}):
            self._data["issues"][new_id] = self._data["issues"].pop(old_id)
            self._save()
            return True, f"Renamed issue '{old_id}' → '{new_id}'."

        return False, f"ID '{old_id}' not found in logs or issues."

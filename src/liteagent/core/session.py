import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from .config import settings

class SessionService:
    def __init__(self):
        self.session_dir = Path(settings.session_dir).expanduser()
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.json"

    def save_session(self, session_id: str, state: Dict[str, Any]) -> None:
        if not session_id:
            return
        path = self._get_path(session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            # Silence persistence errors to avoid interrupting the agent
            pass

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        for file in self.session_dir.glob("*.json"):
            try:
                stat = file.stat()
                sessions.append({
                    "id": file.stem,
                    "mtime": stat.st_mtime,
                    "path": str(file)
                })
            except Exception:
                continue
        # Sort by most recent
        return sorted(sessions, key=lambda x: x["mtime"], reverse=True)

session_service = SessionService()

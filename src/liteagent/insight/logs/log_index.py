import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

class LogIndex:
    """SQLite + FTS5 indexed log storage for fast search."""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS log_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    level TEXT,
                    source TEXT,
                    message TEXT NOT NULL,
                    raw_line TEXT NOT NULL,
                    line_number INTEGER,
                    file_path TEXT NOT NULL,
                    error_codes TEXT,
                    metadata TEXT
                )
            """)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS log_records_fts USING fts5(
                    message,
                    error_codes,
                    raw_line,
                    content=log_records,
                    content_rowid=id
                )
            """)

    def search(self, query: str, is_plain: bool = True, level: Optional[str] = None, last_hours: Optional[int] = None, error_code: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Unified search across all indexed log records."""
        # Stub implementation
        cursor = self.conn.cursor()
        if is_plain:
            # Fake query returning a stub
            return [{
                "timestamp": "2026-05-23T12:00:00Z",
                "level": "ERROR",
                "file_path": "logs/app.log",
                "message": f"Stub log match for {query}"
            }]
        return []

    def get_recent_errors(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        return [{
            "timestamp": "2026-05-23T12:00:00Z",
            "level": "ERROR",
            "file_path": "logs/app.log",
            "message": "Stub error for log_errors"
        }]

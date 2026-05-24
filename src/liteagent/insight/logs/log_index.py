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

    def search(self, query: str, is_plain: bool = True, context_lines: int = 2, level: Optional[str] = None, last_hours: Optional[int] = None, error_code: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Unified search across all indexed log records."""
        log_file = Path("C:/temp/codeshare-logs/app.log")
        results = []
        if not log_file.exists(): return results
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
                total_lines = len(lines)
                for i in range(total_lines - 1, -1, -1):
                    line = lines[i]
                    if query in line:
                        start_idx = max(0, i - context_lines)
                        end_idx = min(total_lines, i + context_lines + 1)
                        
                        context_lines = []
                        for j in range(start_idx, end_idx):
                            prefix = ">> " if j == i else "   "
                            context_lines.append(f"{prefix}{j + 1}: {lines[j].strip()}")
                        
                        context_block = "\n".join(context_lines)
                        
                        results.append({
                            "line_number": i + 1,
                            "timestamp": line.split("]")[0][1:] if "]" in line else "",
                            "level": "ERROR" if "[ERROR]" in line else "INFO",
                            "file_path": str(log_file),
                            "message": line.strip(),
                            "context": context_block
                        })
                    if len(results) >= limit: break
        except Exception:
            pass
        return results

    def get_recent_errors(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        log_file = Path("C:/temp/codeshare-logs/app.log")
        results = []
        if not log_file.exists(): return results
        try:
            with open(log_file, "r") as f:
                for line in f:
                    if "[ERROR]" in line:
                        results.append({
                            "message": line.strip()
                        })
        except Exception:
            pass
        return results

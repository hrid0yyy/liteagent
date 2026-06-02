import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

class KnowledgeGraph:
    """SQLite-backed code knowledge graph."""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Increase timeout and use check_same_thread=False for multi-threaded access
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        # Enable WAL mode for better concurrency (multiple readers + one writer)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    qualified_name TEXT UNIQUE NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    source_code TEXT,
                    class_name TEXT
                )
            """)
            # Migration: add class_name if it doesn't exist
            try:
                self.conn.execute("ALTER TABLE symbols ADD COLUMN class_name TEXT")
            except sqlite3.OperationalError:
                pass # Already exists
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS log_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    method_name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    template TEXT NOT NULL
                )
            """)

    def insert_symbol(self, name: str, qualified_name: str, kind: str, file_path: str, start_line: int, end_line: int, source_code: str, class_name: Optional[str] = None):
        with self.conn:
            self.conn.execute("""
                INSERT INTO symbols (name, qualified_name, kind, file_path, start_line, end_line, source_code, class_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(qualified_name) DO UPDATE SET
                    name=excluded.name,
                    kind=excluded.kind,
                    file_path=excluded.file_path,
                    start_line=excluded.start_line,
                    end_line=excluded.end_line,
                    source_code=excluded.source_code,
                    class_name=excluded.class_name
            """, (name, qualified_name, kind, file_path, start_line, end_line, source_code, class_name))

    def insert_relationship(self, source: str, target: str, kind: str, file_path: str):
        with self.conn:
            self.conn.execute("""
                INSERT INTO relationships (source, target, kind, file_path)
                VALUES (?, ?, ?, ?)
            """, (source, target, kind, file_path))

    def insert_relationships(self, relationships: List[tuple]):
        """Batch insert relationships: List of (source, target, kind, file_path)"""
        if not relationships: return
        with self.conn:
            self.conn.executemany("""
                INSERT INTO relationships (source, target, kind, file_path)
                VALUES (?, ?, ?, ?)
            """, relationships)
            
    def insert_log_template(self, file_path: str, method_name: str, level: str, template: str):
        with self.conn:
            self.conn.execute("""
                INSERT INTO log_templates (file_path, method_name, level, template)
                VALUES (?, ?, ?, ?)
            """, (file_path, method_name, level, template))

    def insert_log_templates(self, templates: List[tuple]):
        """Batch insert log templates: List of (file_path, method_name, level, template)"""
        if not templates: return
        with self.conn:
            self.conn.executemany("""
                INSERT INTO log_templates (file_path, method_name, level, template)
                VALUES (?, ?, ?, ?)
            """, templates)
            
    def clear_file(self, file_path: str):
        """Removes all symbols, relationships, and templates associated with a file."""
        with self.conn:
            self.conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            self.conn.execute("DELETE FROM relationships WHERE file_path = ?", (file_path,))
            self.conn.execute("DELETE FROM log_templates WHERE file_path = ?", (file_path,))


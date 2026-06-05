import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional


def _split_pascal_case(text: str) -> str:
    """Split PascalCase/camelCase into space-separated words for FTS5 indexing.
    e.g. 'HistoryEntry' → 'History Entry', 'XMLParser' → 'XML Parser'
    """
    if not text:
        return text
    # Split at lowercase→uppercase boundary: "historyEntry" → "history Entry"
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Split at uppercase→uppercase+lowercase: "XMLParser" → "XML Parser"
    result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', result)
    return result


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
            # FTS5 virtual table for fast tokenized search on symbols.
            # Standalone (no content= sync) — we manage inserts manually with
            # PascalCase-split values so "HistoryEntry" becomes "History Entry"
            # and FTS5 can match queries like "history entry".
            # 
            # Always drop and recreate FTS5 on startup — it's just an index,
            # and this guarantees consistency after schema changes.
            self.conn.execute("DROP TABLE IF EXISTS symbols_fts")
            # Drop old triggers from previous schema if they exist
            self.conn.execute("DROP TRIGGER IF EXISTS symbols_fts_insert")
            self.conn.execute("DROP TRIGGER IF EXISTS symbols_fts_delete")
            self.conn.execute("DROP TRIGGER IF EXISTS symbols_fts_update")
            
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
                    name, source_code, class_name
                )
            """)
            
            # Rebuild FTS5 index from existing symbols
            self._rebuild_fts_index()

    def _rebuild_fts_index(self):
        """Rebuild the FTS5 index from the symbols table with PascalCase-split values.
        Called on init to handle migration from old schema or empty FTS5.
        """
        # Check if FTS5 is already populated
        cursor = self.conn.execute("SELECT count(*) FROM symbols_fts")
        fts_count = cursor.fetchone()[0]
        cursor = self.conn.execute("SELECT count(*) FROM symbols")
        symbols_count = cursor.fetchone()[0]
        
        # Only rebuild if FTS5 is empty but symbols exist (migration or fresh start)
        if fts_count == 0 and symbols_count > 0:
            cursor = self.conn.execute("SELECT id, name, source_code, class_name FROM symbols")
            rows = cursor.fetchall()
            for row in rows:
                self.conn.execute(
                    "INSERT INTO symbols_fts(rowid, name, source_code, class_name) VALUES (?, ?, ?, ?)",
                    (row[0], _split_pascal_case(row[1]), row[2], _split_pascal_case(row[3] or ""))
                )

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
            # Get the symbol id (works for both INSERT and UPDATE)
            cursor = self.conn.execute(
                "SELECT id FROM symbols WHERE qualified_name=?", (qualified_name,)
            )
            row = cursor.fetchone()
            if row:
                symbol_id = row[0]
                # Remove old FTS5 entry if exists, then insert with PascalCase-split values
                self.conn.execute("DELETE FROM symbols_fts WHERE rowid=?", (symbol_id,))
                self.conn.execute(
                    "INSERT INTO symbols_fts(rowid, name, source_code, class_name) VALUES (?, ?, ?, ?)",
                    (symbol_id, _split_pascal_case(name), source_code, _split_pascal_case(class_name or ""))
                )

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
            
    def get_log_templates(self) -> List[Dict[str, Any]]:
        """Get all log templates grouped by file_path and method_name."""
        cursor = self.conn.execute(
            "SELECT file_path, method_name, level, template FROM log_templates ORDER BY file_path, method_name"
        )
        rows = cursor.fetchall()
        return [{"file_path": r[0], "method_name": r[1], "level": r[2], "template": r[3]} for r in rows]

    def get_methods_for_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all methods in a file with their line ranges."""
        cursor = self.conn.execute(
            "SELECT name, start_line, end_line, class_name FROM symbols WHERE kind='Function' AND file_path=? ORDER BY start_line",
            (file_path,)
        )
        rows = cursor.fetchall()
        return [{"name": r[0], "start_line": r[1], "end_line": r[2], "class_name": r[3]} for r in rows]

    def find_matching_templates(self, log_line: str) -> List[Dict[str, Any]]:
        """Find all log templates that match a given log line.
        Returns list of dicts with file_path, method_name, level, template, and method line range.
        """
        cursor = self.conn.execute(
            "SELECT file_path, method_name, level, template FROM log_templates"
        )
        rows = cursor.fetchall()
        
        matches = []
        for row in rows:
            file_path, method_name, level, template = row
            try:
                if re.search(template, log_line, re.IGNORECASE):
                    # Get method line range
                    method_cursor = self.conn.execute(
                        "SELECT start_line, end_line FROM symbols WHERE name=? AND file_path=? AND kind='Function'",
                        (method_name, file_path)
                    )
                    method_info = method_cursor.fetchone()
                    result = {
                        "file_path": file_path,
                        "method_name": method_name,
                        "level": level,
                    }
                    if method_info:
                        result["start_line"] = method_info[0]
                        result["end_line"] = method_info[1]
                    matches.append(result)
            except re.error:
                pass
        
        return matches

    def clear_file(self, file_path: str):
        """Removes all symbols, relationships, and templates associated with a file."""
        with self.conn:
            # Get symbol IDs before deleting so we can clean up FTS5
            cursor = self.conn.execute("SELECT id FROM symbols WHERE file_path = ?", (file_path,))
            symbol_ids = [row[0] for row in cursor.fetchall()]
            if symbol_ids:
                placeholders = ",".join("?" * len(symbol_ids))
                self.conn.execute(f"DELETE FROM symbols_fts WHERE rowid IN ({placeholders})", symbol_ids)
            self.conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            self.conn.execute("DELETE FROM relationships WHERE file_path = ?", (file_path,))
            self.conn.execute("DELETE FROM log_templates WHERE file_path = ?", (file_path,))


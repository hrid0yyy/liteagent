import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

class KnowledgeGraph:
    """SQLite-backed code knowledge graph."""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
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
                    source_code TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL
                )
            """)

    def insert_symbol(self, name: str, qualified_name: str, kind: str, file_path: str, start_line: int, end_line: int, source_code: str):
        with self.conn:
            self.conn.execute("""
                INSERT INTO symbols (name, qualified_name, kind, file_path, start_line, end_line, source_code)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(qualified_name) DO UPDATE SET
                    name=excluded.name,
                    kind=excluded.kind,
                    file_path=excluded.file_path,
                    start_line=excluded.start_line,
                    end_line=excluded.end_line,
                    source_code=excluded.source_code
            """, (name, qualified_name, kind, file_path, start_line, end_line, source_code))

    def insert_relationship(self, source: str, target: str, kind: str, file_path: str):
        with self.conn:
            self.conn.execute("""
                INSERT INTO relationships (source, target, kind, file_path)
                VALUES (?, ?, ?, ?)
            """, (source, target, kind, file_path))
            
    def clear_file(self, file_path: str):
        """Removes all symbols and relationships associated with a file."""
        with self.conn:
            self.conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            self.conn.execute("DELETE FROM relationships WHERE file_path = ?", (file_path,))
    
    def trace_calls(self, symbol: str, direction: str = "both", depth: int = 3, max_nodes: int = 50) -> Dict[str, Any]:
        """
        Traces calls by querying the relationships table.
        """
        cursor = self.conn.cursor()
        callers = []
        callees = []
        
        if direction in ("both", "callers"):
            cursor.execute("SELECT DISTINCT source FROM relationships WHERE target = ?", (symbol,))
            callers = [row[0] for row in cursor.fetchall()]
            
        if direction in ("both", "callees"):
            cursor.execute("SELECT DISTINCT target FROM relationships WHERE source = ?", (symbol,))
            callees = [row[0] for row in cursor.fetchall()]
            
        return {
            "symbol": symbol,
            "direction": direction,
            "depth": depth,
            "nodes_traversed": len(callers) + len(callees),
            "callers": callers,
            "callees": callees
        }
    
    def find_symbol_by_snippet(self, snippet: str) -> Optional[Dict[str, Any]]:
        """
        Helper for trace_error_to_code to find a function containing a specific log snippet.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT qualified_name, file_path, start_line, source_code FROM symbols WHERE source_code LIKE ?", (f"%{snippet}%",))
        row = cursor.fetchone()
        if row:
            return {
                "qualified_name": row[0],
                "file_path": row[1],
                "line": row[2],
                "code": row[3]
            }
        return None

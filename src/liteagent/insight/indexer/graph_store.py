import sqlite3
from pathlib import Path
from typing import List, Dict, Any

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
    
    def trace_calls(self, symbol: str, direction: str = "both", depth: int = 3, max_nodes: int = 50) -> Dict[str, Any]:
        """
        Stub for tracing calls.
        In a real implementation, this would perform a recursive BFS/DFS on the `relationships` table.
        """
        # For demonstration
        return {
            "symbol": symbol,
            "direction": direction,
            "depth": depth,
            "nodes_traversed": 0,
            "callers": [],
            "callees": []
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

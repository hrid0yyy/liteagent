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
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS log_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    method_name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    template TEXT NOT NULL
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
            
    def insert_log_template(self, file_path: str, method_name: str, level: str, template: str):
        with self.conn:
            self.conn.execute("""
                INSERT INTO log_templates (file_path, method_name, level, template)
                VALUES (?, ?, ?, ?)
            """, (file_path, method_name, level, template))
            
    def clear_file(self, file_path: str):
        """Removes all symbols, relationships, and templates associated with a file."""
        with self.conn:
            self.conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            self.conn.execute("DELETE FROM relationships WHERE file_path = ?", (file_path,))
            self.conn.execute("DELETE FROM log_templates WHERE file_path = ?", (file_path,))
    
    def trace_calls(self, symbol: str, direction: str = "both", depth: int = 3, max_nodes: int = 50) -> Dict[str, Any]:
        """
        Traces calls by querying the relationships table using a recursive BFS search.
        """
        cursor = self.conn.cursor()
        
        def bfs(start_symbol: str, target_col: str, search_col: str) -> List[str]:
            visited = set()
            queue = [(start_symbol, 0)]
            results = set()
            
            while queue and len(results) < max_nodes:
                curr, curr_depth = queue.pop(0)
                if curr_depth >= depth:
                    continue
                    
                cursor.execute(f"SELECT DISTINCT {target_col} FROM relationships WHERE {search_col} = ?", (curr,))
                for row in cursor.fetchall():
                    node = row[0]
                    if node not in visited:
                        visited.add(node)
                        results.add(node)
                        queue.append((node, curr_depth + 1))
            return list(results)

        callers = []
        callees = []
        
        if direction in ("both", "callers"):
            # Callers: Who calls the symbol? (Find sources where target = symbol)
            callers = bfs(symbol, target_col="source", search_col="target")
            
        if direction in ("both", "callees"):
            # Callees: Who does the symbol call? (Find targets where source = symbol)
            callees = bfs(symbol, target_col="target", search_col="source")
            
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

    def get_log_templates(self, module: Optional[str] = None, level: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        query = "SELECT file_path, method_name, level, template FROM log_templates WHERE 1=1"
        params = []
        
        if module:
            query += " AND (file_path LIKE ? OR method_name LIKE ?)"
            params.extend([f"%{module}%", f"%{module}%"])
            
        if level:
            query += " AND level = ?"
            params.append(level)
        query += " ORDER BY LENGTH(template) DESC"
        
        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                "file_path": row[0],
                "method_name": row[1],
                "level": row[2],
                "template": row[3]
            })
        return results

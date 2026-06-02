import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from ...core.config import settings

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

    def _match_lines(self, lines: list, query: str, is_plain: bool) -> list:
        """
        Returns list of (line_index, is_fuzzy) tuples.
        Runs stages in order, stops as soon as a stage produces results.
        """
        query_lower = query.lower()

        # Stage 1 — case-insensitive exact match
        hits = [(i, False) for i, line in enumerate(lines) if query_lower in line.lower()]
        if hits:
            # We want newest logs first, so reverse hits (assuming search() handles reverse order)
            # Actually search() loop is backward, so we return indices as found
            return hits

        # Stage 2 — regex (only when is_plain=False)
        if not is_plain:
            import re
            try:
                hits = [(i, False) for i, line in enumerate(lines)
                        if re.search(query, line, re.IGNORECASE)]
                if hits:
                    return hits
            except Exception:
                pass

        # Stage 3 — RapidFuzz partial_ratio
        try:
            from rapidfuzz import fuzz
            THRESHOLD = 70
            scored = []
            for i, line in enumerate(lines):
                score = fuzz.partial_ratio(query_lower, line.lower())
                if score >= THRESHOLD:
                    scored.append((score, i))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [(i, True) for _, i in scored]
        except ImportError:
            return []

    def search(self, query: str, is_plain: bool = True, context_lines: int = 2, last_hours: Optional[int] = None, limit: int = 1) -> List[Dict[str, Any]]:
        """Unified search across all indexed log records."""
        results = []
        for path_str in settings.insight_log_paths:
            log_file = Path(path_str)
            if not log_file.exists(): continue
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    total_lines = len(lines)
                    
                    matched = self._match_lines(lines, query, is_plain)
                    
                    # If it's stage 1/2, they are in forward order, but we want newest first
                    # If it's stage 3, they are in relevance order.
                    # For consistency with old behavior (backward scan), let's sort indices desc if not fuzzy
                    is_fuzzy = any(m[1] for m in matched)
                    if not is_fuzzy:
                        matched.sort(key=lambda x: x[0], reverse=True)

                    for i, fuzzy in matched:
                        line = lines[i]
                        
                        start_idx = max(0, i - context_lines)
                        end_idx = min(total_lines, i + context_lines + 1)
                        
                        line_context = []
                        for j in range(start_idx, end_idx):
                            prefix = ">> " if j == i else "   "
                            line_context.append(f"{prefix}{j + 1}: {lines[j].strip()}")
                        
                        context_block = "\n".join(line_context)
                        
                        results.append({
                            "line_number": i + 1,
                            "timestamp": line.split("]")[0][1:] if "]" in line else "",
                            "level": "ERROR" if "[ERROR]" in line else "INFO",
                            "file_path": str(log_file),
                            "message": line.strip(),
                            "context": context_block,
                            "fuzzy": fuzzy
                        })
                        if len(results) >= limit: break
            except Exception:
                pass
            if len(results) >= limit: break
        return results

    def search_indexed(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search ingested log records using FTS5. Falls back to LIKE on syntax error."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT r.timestamp, r.level, r.file_path, r.line_number, r.message
                FROM log_records r
                JOIN log_records_fts fts ON r.id = fts.rowid
                WHERE log_records_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            rows = cursor.fetchall()
        except Exception:
            cursor.execute("""
                SELECT timestamp, level, file_path, line_number, message
                FROM log_records
                WHERE message LIKE ? OR raw_line LIKE ?
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            rows = cursor.fetchall()
            
        results = []
        for row in rows:
            results.append({
                "timestamp": row[0],
                "level": row[1],
                "file_path": row[2],
                "line_number": row[3],
                "message": row[4]
            })
        return results

    def get_recent_errors(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        results = []
        for path_str in settings.insight_log_paths:
            log_file = Path(path_str)
            if not log_file.exists(): continue
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "[ERROR]" in line:
                            results.append({
                                "message": line.strip(),
                                "file_path": str(log_file)
                            })
            except Exception:
                pass
        return results

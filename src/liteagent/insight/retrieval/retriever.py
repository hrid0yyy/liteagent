import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

# Maximum source code lines to show before truncating.
# If a result has more lines than this, it gets truncated with a hint to use read_file.
MAX_SOURCE_LINES = 50


class HybridRetriever:
    """Multi-stage code retrieval: FTS5 → BM25 → RapidFuzz."""

    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir
        self._bm25 = None
        self._bm25_ids = None
        self._bm25_stale = True

    def mark_stale(self):
        """Mark the BM25 index as stale so it rebuilds on next search."""
        self._bm25_stale = True

    def _split_pascal_case(self, text: str) -> str:
        """Split PascalCase/camelCase into space-separated words.
        e.g. 'HistoryEntry' → 'History Entry', 'XMLParser' → 'XML Parser'
        """
        if not text:
            return text
        result = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', result)
        return result

    def _tokenize(self, text: str) -> List[str]:
        """Split text into lowercase alphanumeric tokens for BM25.
        Handles PascalCase: 'HistoryEntry' → ['history', 'entry']
        """
        # First split PascalCase so tokens are separated
        split = self._split_pascal_case(text)
        return [t.lower() for t in re.split(r'[^a-zA-Z0-9]+', split) if t]

    def _build_bm25_index(self):
        """Build BM25 index from all symbols in SQLite."""
        from rank_bm25 import BM25Okapi

        db_path = self.persist_dir / "knowledge.db"
        if not db_path.exists():
            self._bm25 = None
            self._bm25_ids = None
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, class_name, source_code FROM symbols")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            self._bm25 = None
            self._bm25_ids = None
            return

        self._bm25_ids = [row[0] for row in rows]
        corpus = []
        for row in rows:
            doc = f"{row[1]} {row[2] or ''} {row[3] or ''}"
            corpus.append(self._tokenize(doc))

        self._bm25 = BM25Okapi(corpus)
        self._bm25_stale = False

    def _truncate_source(self, source_code: str, start_line: int, end_line: int) -> str:
        """Truncate source code if it exceeds MAX_SOURCE_LINES, adding a read_file hint."""
        lines = source_code.splitlines()
        if len(lines) <= MAX_SOURCE_LINES:
            return source_code
        truncated = "\n".join(lines[:MAX_SOURCE_LINES])
        truncated += f"\n// ... (Function/class line range {start_line}-{end_line}. Use the read_file tool to read the whole thing)"
        return truncated

    def _rank_by_name_match(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Re-rank results using 3-tier ranking:
        
        1. Perfect name match: all query tokens match the symbol's name or class_name
        2. Partial name match: some query tokens match name or class_name
        3. Code-only match: no name/class_name overlap (matched via source_code)
        
        Within each tier, original order is preserved.
        """
        query_tokens = set(self._tokenize(query))
        
        perfect_matches = []
        partial_matches = []
        code_only_matches = []
        
        for r in results:
            # Check both the symbol name (e.g. "HistoryEntry") and class_name
            symbol_tokens = set(self._tokenize(r.get("name", "") or ""))
            class_tokens = set(self._tokenize(r.get("class_name", "") or ""))
            all_name_tokens = symbol_tokens | class_tokens
            
            overlap = query_tokens & all_name_tokens
            
            if not overlap:
                code_only_matches.append(r)
            elif overlap == query_tokens:
                # All query tokens found in name/class_name — perfect match
                perfect_matches.append(r)
            else:
                # Some but not all query tokens match — partial match
                partial_matches.append(r)
        
        return perfect_matches + partial_matches + code_only_matches

    def search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        db_path = self.persist_dir / "knowledge.db"
        if not db_path.exists():
            return []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        results = []

        # Stage 1: FTS5 tokenized search
        results = self._search_fts5(cursor, query, top_k)
        if results:
            results = self._rank_by_name_match(results, query)[:top_k]
            conn.close()
            return self._apply_truncation(results)

        # Stage 2: BM25 scoring
        results = self._search_bm25(cursor, query, top_k)
        if results:
            results = self._rank_by_name_match(results, query)[:top_k]
            conn.close()
            return self._apply_truncation(results)

        # Stage 3: RapidFuzz fuzzy match
        results = self._search_fuzzy(cursor, query, top_k)
        conn.close()
        return self._apply_truncation(results)

    def _search_fts5(self, cursor, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Stage 1: Fast tokenized search using SQLite FTS5."""
        # Tokenize with PascalCase splitting so "history entry" matches "History Entry"
        tokens = self._tokenize(query)
        if not tokens:
            return []
        fts_query = " ".join(tokens)

        try:
            # FTS5 is standalone (no content=sync), so we JOIN on rowid = symbols.id
            cursor.execute("""
                SELECT s.file_path, s.name, s.class_name, s.source_code, s.start_line, s.end_line
                FROM symbols s
                JOIN symbols_fts fts ON s.id = fts.rowid
                WHERE symbols_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (fts_query, top_k * 5))
            rows = cursor.fetchall()
        except Exception:
            return []

        results = []
        for row in rows:
            results.append({
                "file_path": row[0],
                "name": row[1],
                "class_name": row[2] or "",
                "source_code": row[3],
                "start_line": row[4],
                "end_line": row[5],
            })
        return results

    def _search_bm25(self, cursor, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Stage 2: BM25Okapi scoring for proper TF-IDF ranking."""
        if self._bm25_stale or self._bm25 is None:
            self._build_bm25_index()

        if self._bm25 is None or self._bm25_ids is None:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        scores = self._bm25.get_scores(tokenized_query)
        # Get top_k indices by score
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for idx in ranked:
            if scores[idx] <= 0:
                break
            if len(results) >= top_k:
                break

            symbol_id = self._bm25_ids[idx]
            cursor.execute(
                "SELECT file_path, name, class_name, source_code, start_line, end_line FROM symbols WHERE id=?",
                (symbol_id,)
            )
            row = cursor.fetchone()
            if row:
                results.append({
                    "file_path": row[0],
                    "name": row[1],
                    "class_name": row[2] or "",
                    "source_code": row[3],
                    "start_line": row[4],
                    "end_line": row[5],
                })
        return results

    def _search_fuzzy(self, cursor, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Stage 3: RapidFuzz partial_ratio for typos, partial names, rephrasing."""
        try:
            from rapidfuzz import fuzz
        except ImportError:
            return []

        cursor.execute("SELECT file_path, name, class_name, source_code, start_line, end_line FROM symbols")
        rows = cursor.fetchall()

        if not rows:
            return []

        THRESHOLD = 65
        query_lower = query.lower()
        scored = []

        for row in rows:
            name = row[1] or ""
            class_name = row[2] or ""
            # Score against both name and class_name, take the best
            name_score = fuzz.partial_ratio(query_lower, name.lower())
            class_score = fuzz.partial_ratio(query_lower, class_name.lower())
            best_score = max(name_score, class_score)

            if best_score >= THRESHOLD:
                scored.append((best_score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, row in scored[:top_k]:
            results.append({
                "file_path": row[0],
                "name": row[1],
                "class_name": row[2] or "",
                "source_code": row[3],
                "start_line": row[4],
                "end_line": row[5],
            })
        return results

    def _apply_truncation(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply source code truncation to all results."""
        for r in results:
            r["source_code"] = self._truncate_source(
                r["source_code"], r.get("start_line", 0), r.get("end_line", 0)
            )
        return results

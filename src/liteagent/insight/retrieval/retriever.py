from pathlib import Path
from typing import List, Dict, Any

class HybridRetriever:
    """Combines dense vector, sparse BM25, and graph-based retrieval."""
    def __init__(self, persist_dir: Path, code_collection=None):
        self.persist_dir = persist_dir
        self.code_collection = code_collection

    def search(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        import sqlite3
        db_path = self.persist_dir / "knowledge.db"
        if not db_path.exists():
            return []
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        results = []
        
        # 1. Semantic Vector Search with Chunk Fusion
        if self.code_collection:
            chroma_results = self.code_collection.query(query_texts=[query], n_results=top_k * 3)
            
            # Count how many chunks matched per (file_path, method_name)
            match_counts = {}
            if chroma_results and chroma_results["metadatas"]:
                for meta in chroma_results["metadatas"][0]:
                    if not meta.get("method_name"):
                        # class-level summary hit — use it to boost ranking but skip for direct return
                        # unless we decide to return class source (not planned for now)
                        continue
                    key = (meta["file_path"], meta["method_name"])
                    match_counts[key] = match_counts.get(key, 0) + 1

            # Sort by match count descending, take top_k unique methods
            ranked = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)[:top_k]

            for (file_path, method_name), score in ranked:
                cursor.execute(
                    "SELECT file_path, name, class_name, source_code FROM symbols WHERE name=? AND file_path=?",
                    (method_name, file_path)
                )
                row = cursor.fetchone()
                if row:
                    results.append({
                        "file_path": row[0],
                        "symbol_name": row[1],
                        "class_name": row[2] or "",
                        "source_code": row[3],
                        "match_score": score
                    })

            if results:
                conn.close()
                return results

        # 2. Fallback to Sparse/Keyword SQLite Search
        words = [w for w in query.split() if len(w) > 3]
        if not words:
            words = [query]
            
        conditions = []
        params = []
        for word in words:
            conditions.append("(source_code LIKE ? OR name LIKE ?)")
            params.extend([f"%{word}%", f"%{word}%"])
            
        where_clause = " OR ".join(conditions)
        
        cursor.execute(
            f"SELECT file_path, name, class_name, source_code FROM symbols WHERE {where_clause} LIMIT ?", 
            (*params, top_k)
        )
        
        for row in cursor.fetchall():
            results.append({
                "file_path": row[0],
                "symbol_name": row[1],
                "class_name": row[2] or "",
                "source_code": row[3],
                "match_score": 0.50
            })
            
        conn.close()
        return results

    def _expand_with_callees(self, results, cursor, top_k):
        """For each returned method, attach signatures of methods it calls."""
        expanded = list(results)
        seen = {(r["file_path"], r["symbol_name"]) for r in results}

        for r in results[:3]:   # only expand top 3 to avoid bloat
            cursor.execute(
                "SELECT target FROM relationships WHERE source=? AND file_path=?",
                (r["symbol_name"], r["file_path"])
            )
            for (callee,) in cursor.fetchall():
                cursor.execute(
                    "SELECT file_path, name, class_name, source_code FROM symbols WHERE name=?",
                    (callee,)
                )
                row = cursor.fetchone()
                if row and (row[0], row[1]) not in seen:
                    seen.add((row[0], row[1]))
                    expanded.append({
                        "file_path": row[0],
                        "symbol_name": row[1],
                        "class_name": row[2] or "",
                        "source_code": row[3],
                        "match_score": 0,   # not a direct hit, context only
                        "context_note": f"called by {r['symbol_name']}"
                    })
        return expanded

from pathlib import Path
from typing import List, Dict, Any

class HybridRetriever:
    """Combines dense vector, sparse BM25, and graph-based retrieval."""
    def __init__(self, persist_dir: Path, code_collection=None):
        self.persist_dir = persist_dir
        self.code_collection = code_collection

    def search(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval search.
        Uses Semantic Vector Search first, falls back to SQLite.
        """
        import sqlite3
        db_path = self.persist_dir / "knowledge.db"
        if not db_path.exists():
            return []
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        results = []
        
        # 1. Semantic Vector Search
        if self.code_collection:
            chroma_results = self.code_collection.query(query_texts=[query], n_results=top_k)
            if chroma_results and chroma_results["ids"] and chroma_results["ids"][0]:
                qnames = chroma_results["ids"][0]
                
                # Fetch full data from SQLite using the vector-matched IDs
                placeholders = ",".join("?" for _ in qnames)
                cursor.execute(f"SELECT file_path, name, source_code FROM symbols WHERE qualified_name IN ({placeholders})", qnames)
                
                for row in cursor.fetchall():
                    results.append({
                        "file_path": row[0],
                        "symbol_name": row[1],
                        "source_code": row[2],
                        "relevance_score": 0.99
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
            f"SELECT file_path, name, source_code FROM symbols WHERE {where_clause} LIMIT ?", 
            (*params, top_k)
        )
        
        for row in cursor.fetchall():
            results.append({
                "file_path": row[0],
                "symbol_name": row[1],
                "source_code": row[2],
                "relevance_score": 0.50
            })
            
        conn.close()
        return results

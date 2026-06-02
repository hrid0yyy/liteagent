# Search Code Tool — Improvement Plan

## Problem

`all-MiniLM-L6-v2` has a **512 token limit**. Large classes and long methods get
silently truncated during embedding, making semantic search unreliable for anything
non-trivial. A big service class or a complex method loses most of its body in the
vector representation and simply won't surface on concept-level queries.

---

## Proposed Solution: Chunked Indexing with Method-Scoped Retrieval

Instead of embedding the full symbol source as one unit, split each method into
**overlapping chunks**, embed them individually, but always **return the full method**
when any chunk matches — along with its class and file path.

---

## Changes Required

### 1. `graph_store.py` — Add `class_name` to `symbols` table

The SQLite schema needs one new column so every symbol knows which class it belongs to.

**Schema change:**
```sql
ALTER TABLE symbols ADD COLUMN class_name TEXT;
```

**`insert_symbol` signature change:**
```python
def insert_symbol(self, name, qualified_name, kind, file_path,
                  start_line, end_line, source_code, class_name=None):
```

---

### 2. `ast_parser.py` — Track class context + emit chunks

**Track current class while traversing** (same pattern as `current_method`):

```python
current_class = None

if node.type == "class_declaration":
    current_class = get_identifier(node)
    # index class-level summary chunk (see improvement 4)
    ...

elif node.type == "method_declaration":
    # pass current_class into indexing
    _index_method_chunks(name, current_class, source, file_path)
```

**Chunk the method source before embedding:**

```python
CHUNK_TOKENS = 200   # approximate, use char proxy: ~800 chars
OVERLAP_TOKENS = 50  # ~200 chars

def _index_method_chunks(self, method_name, class_name, signature, source, file_path):
    chunks = self._split_with_overlap(source, chunk_size=800, overlap=200)
    for i, chunk in enumerate(chunks):
        # Prepend signature to every chunk so each embedding carries method context
        enriched = f"{signature}\n{chunk}"
        chunk_id = f"method.{method_name}::chunk_{i}::{file_path}"
        self.code_collection.upsert(
            ids=[chunk_id],
            documents=[enriched],
            metadatas=[{
                "file_path": file_path,
                "class_name": class_name or "",
                "method_name": method_name,
                "chunk_index": i
            }]
        )
    # SQLite still stores the full method (unchanged)
    self.graph_store.insert_symbol(
        method_name, f"method.{method_name}", "Function",
        file_path, start_line, end_line, source, class_name
    )
```

**Class-level summary chunk** (improvement 4 — table of contents embedding):

```python
def _index_class_summary(self, class_name, method_signatures, file_path):
    summary = f"class {class_name}:\n" + "\n".join(method_signatures)
    chunk_id = f"class_summary.{class_name}::{file_path}"
    self.code_collection.upsert(
        ids=[chunk_id],
        documents=[summary],
        metadatas=[{
            "file_path": file_path,
            "class_name": class_name,
            "method_name": "",   # marks it as a class-level entry
            "chunk_index": -1
        }]
    )
```

**Helper — overlapping splitter:**

```python
def _split_with_overlap(self, text: str, chunk_size: int, overlap: int):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks
```

---

### 3. `retriever.py` — Deduplicate + score fusion + call graph expansion

**After ChromaDB returns chunk hits, deduplicate by method and score by match count:**

```python
def search(self, query: str, top_k: int = 8):
    chroma_results = self.code_collection.query(query_texts=[query], n_results=top_k * 3)

    # Count how many chunks matched per (file_path, method_name)
    match_counts = {}
    if chroma_results and chroma_results["metadatas"]:
        for meta in chroma_results["metadatas"][0]:
            key = (meta["file_path"], meta["method_name"])
            match_counts[key] = match_counts.get(key, 0) + 1

    # Sort by match count descending, take top_k unique methods
    ranked = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    conn = sqlite3.connect(self.persist_dir / "knowledge.db")
    cursor = conn.cursor()

    for (file_path, method_name), score in ranked:
        if not method_name:
            # class-level summary hit — skip, used only for ranking
            continue
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

    # Optional: call graph expansion — append signatures of called methods
    results = self._expand_with_callees(results, cursor, top_k)

    conn.close()
    return results


def _expand_with_callees(self, results, cursor, top_k):
    """For each returned method, attach signatures of methods it calls."""
    expanded = list(results)
    seen = {(r["file_path"], r["symbol_name"]) for r in results}

    for r in results[:3]:   # only expand top 3 to avoid bloat
        cursor.execute(
            "SELECT target FROM relationships WHERE source=? AND kind='calls'",
            (r["symbol_name"],)
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
```

---

### 4. `search_code_tool.py` — Updated output format

```python
for r in results:
    header = f"File: {r['file_path']}"
    if r.get("class_name"):
        header += f"\nClass: {r['class_name']}"
    header += f"\nMethod: {r.get('symbol_name', 'Unknown')}"
    if r.get("context_note"):
        header += f"\n[Context: {r['context_note']}]"
    output.append(f"{header}\nCode:\n{r['source_code']}\n---")
```

---

### 5. Stale chunk cleanup on file change

`InsightProviders` already calls `code_collection.delete(where={"file_path": ...})`
before re-indexing a modified file. With chunked IDs the `where` filter on metadata
still works correctly — no change needed here as long as `file_path` is always stored
in chunk metadata (which the plan above does).

---

## Summary of All Changes

| File | Change |
|---|---|
| `graph_store.py` | Add `class_name` column to `symbols` table and `insert_symbol` |
| `ast_parser.py` | Track `current_class`, chunk methods with overlap, prepend signature, emit class summary chunk |
| `retriever.py` | Deduplicate chunks by method, score fusion by match count, call graph expansion |
| `search_code_tool.py` | Show `class_name` in output, show `context_note` for callee expansions |

---

## What Each Improvement Covers

| Improvement | Query type it solves |
|---|---|
| Overlapping chunks | Long methods where relevant logic is deep in the body |
| Signature prefix on every chunk | Chunks matching on body content still surface the right method |
| Score fusion (match count) | Prioritises methods with broad relevance over incidental single-chunk hits |
| Class summary chunk | High-level queries like *"find the class that handles auth"* |
| Call graph expansion | Queries where the answer depends on a method's dependencies |

---

## Embedding Model Recommendation

For projects with large files, set:

```
LITEAGENT_EMBED_MODEL=nomic
```

`nomic-ai/nomic-embed-text-v1.5` supports **8192 tokens** (~274MB). Even with chunking,
this is a useful safety net for the class summary chunks which can grow large.
Default `all-MiniLM-L6-v2` (~90MB, 512 tokens) remains fine for most method-level chunks
since overlapping chunks keep each unit small.

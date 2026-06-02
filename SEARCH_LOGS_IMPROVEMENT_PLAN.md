# Search Logs Tool — Improvement Plan

## Problem

The `search_logs` tool uses **exact substring matching** (`query in line`) to scan
log files. This means the LLM must pass the exact string as it appears in the log.
In practice the LLM rephrases method names, uses different casing, or adds extra
words — and the search silently returns nothing.

### Specific failure modes

| LLM input | Actual log content | Result |
|---|---|---|
| `"functionA"` | `[INFO] FunctionA started` | ❌ case mismatch |
| `"Function A"` | `[INFO] FunctionA started` | ❌ space in query |
| `"FuncA log"` | `[INFO] FunctionA started` | ❌ extra word |
| `"check FunctionAs"` | `[INFO] FunctionAs completed` | ❌ prefix not matched |

### Secondary problem — FTS5 is built but never used

`_init_db()` creates a `log_records_fts` virtual table using SQLite FTS5, but the
`search()` method ignores it entirely and scans raw files line by line. The
infrastructure for fast indexed search is already there, just wired to nothing.

---

## Proposed Solution: 3-Stage Search Pipeline + RapidFuzz

Replace the single `query in line` check with a ranked 3-stage pipeline. The fuzzy
stage uses **RapidFuzz** — a battle-tested Python library for fuzzy string matching
— instead of a hand-rolled token scorer.

`rapidfuzz` is not in `pyproject.toml` yet. Add it:

```toml
dependencies = [
    ...
    "rapidfuzz>=3.0.0",
]
```

### Why RapidFuzz over a custom token pipeline

| | Custom token split | RapidFuzz |
|---|---|---|
| Handles typos | ❌ | ✅ |
| Partial name match | ✅ (if token present) | ✅ (partial_ratio) |
| Extra words in query | ✅ (score by count) | ✅ (token_set_ratio) |
| Casing | ✅ (lowercased) | ✅ |
| Dependency | none | ~1MB, pure Python |
| Already battle-tested | ❌ | ✅ |

The right scorer to use is `fuzz.partial_ratio` — it finds the best matching
substring within the line, so `"FunctionAs"` inside a long log line still scores
high even with surrounding text.

### Pipeline stages

```
Stage 1 — Case-insensitive exact match     (fast, zero deps, covers casing)
Stage 2 — Regex match                      (when is_plain=False)
Stage 3 — RapidFuzz partial_ratio          (handles typos, partial names, rephrasing)
```

Each stage is a fallback — if stage 1 returns results, stages 2 and 3 are skipped.

---

## Changes Required

### 1. `pyproject.toml` — Add RapidFuzz

```toml
"rapidfuzz>=3.0.0",
```

---

### 2. `log_index.py` — Fix `search()` + add `_match_lines()`

```python
def search(self, query: str, is_plain: bool = True, context_lines: int = 2,
           level=None, last_hours=None, error_code=None, limit: int = 50):

    results = []

    for path_str in settings.insight_log_paths:
        log_file = Path(path_str)
        if not log_file.exists():
            continue

        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            continue

        matched = self._match_lines(lines, query, is_plain)

        for i, fuzzy in matched:
            line = lines[i]

            if level and f"[{level.upper()}]" not in line:
                continue

            start_idx = max(0, i - context_lines)
            end_idx = min(len(lines), i + context_lines + 1)
            context_block = "\n".join(
                f"{'>> ' if j == i else '   '}{j+1}: {lines[j].strip()}"
                for j in range(start_idx, end_idx)
            )

            results.append({
                "line_number": i + 1,
                "timestamp": line.split("]")[0][1:] if "]" in line else "",
                "level": "ERROR" if "[ERROR]" in line else
                         "WARN"  if "[WARN]"  in line else "INFO",
                "file_path": str(log_file),
                "message": line.strip(),
                "context": context_block,
                "fuzzy": fuzzy   # flag for the tool layer
            })

            if len(results) >= limit:
                break

        if len(results) >= limit:
            break

    return results


def _match_lines(self, lines: list, query: str, is_plain: bool) -> list:
    """
    Returns list of (line_index, is_fuzzy) tuples.
    Runs stages in order, stops as soon as a stage produces results.
    """
    query_lower = query.lower()

    # Stage 1 — case-insensitive exact match
    hits = [(i, False) for i, line in enumerate(lines) if query_lower in line.lower()]
    if hits:
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
    # Scores each line by how well the query matches any substring within it.
    # Threshold 70 avoids noise while catching typos and partial names.
    from rapidfuzz import fuzz

    THRESHOLD = 70
    scored = []
    for i, line in enumerate(lines):
        score = fuzz.partial_ratio(query_lower, line.lower())
        if score >= THRESHOLD:
            scored.append((score, i))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [(i, True) for _, i in scored]
```

---

### 3. `log_index.py` — Wire up FTS5 for ingested records

The `log_records_fts` virtual table is created but never queried. Add a proper
`search_indexed()` method that uses it. FTS5 handles tokenization natively and is
fast on large SQLite log databases.

```python
def search_indexed(self, query: str, limit: int = 50):
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
        return cursor.fetchall()
    except Exception:
        cursor.execute("""
            SELECT timestamp, level, file_path, line_number, message
            FROM log_records
            WHERE message LIKE ? OR raw_line LIKE ?
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit))
        return cursor.fetchall()
```

> **Note:** FTS5 `MATCH` syntax is strict — passing a plain string like
> `"FunctionAs log"` treats it as two separate tokens and ANDs them. This is
> usually what you want. For phrase search use `"FunctionAs log"` (quoted inside
> the query string).

---

### 4. `search_logs_tool.py` — Surface fuzzy match note to the LLM

```python
for r in results:
    note = " [fuzzy match]" if r.get("fuzzy") else ""
    output.append(
        f"[{r.get('timestamp', 'UNKNOWN')}] {r.get('level', 'INFO')}"
        f" - Line {r.get('line_number', '?')}"
        f" - {r.get('file_path', 'unknown')}{note}\n"
        f"Context:\n{r.get('context', '')}\n---"
    )
```

This lets the LLM know when a result came from fuzzy matching so it can caveat
its answer appropriately — e.g. *"Found a likely match but it may not be exact."*

---

## Summary of Changes

| File | Change |
|---|---|
| `pyproject.toml` | Add `rapidfuzz>=3.0.0` |
| `log_index.py` — `search()` | Replace `query in line` with 3-stage pipeline, pass `fuzzy` flag in results |
| `log_index.py` — `_match_lines()` | New helper: exact → regex → RapidFuzz `partial_ratio` |
| `log_index.py` — `search_indexed()` | New method: FTS5-backed search for ingested records |
| `search_logs_tool.py` | Show `[fuzzy match]` label when result came from stage 3 |

---

## What Each Stage Covers

| Stage | Library | Handles |
|---|---|---|
| Case-insensitive exact | stdlib | `"functionA"` finding `"FunctionA"` |
| Regex | stdlib `re` | Patterns like `"Func.*log"`, `"Func[A-Z]"` |
| RapidFuzz `partial_ratio` | `rapidfuzz` | Typos, partial names, extra words, rephrasing |
| FTS5 (indexed records) | SQLite built-in | Fast tokenized search on large ingested log DBs |

---

## Example: Before vs After

Query from LLM: `"check FunctionAs log"`

**Before:** `"check FunctionAs log" in line` → no match → `"No logs found"`

**After:**
- Stage 1: `"check functionas log"` in `line.lower()` → no match
- Stage 2: skipped (`is_plain=True`)
- Stage 3: `fuzz.partial_ratio("check functionas log", "[info] functionas completed")` → score ~82 → **matched, flagged as fuzzy**

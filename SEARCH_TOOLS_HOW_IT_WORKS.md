# Search Tools — How They Work

This document describes how the `search_code` and `search_logs` tools work end-to-end based on the **current implementation**.

> **Status as of June 2026:** Both `search_code` and `search_logs` are **active**.

---

## 1. Search Code Tool

### Current Status: ✅ ACTIVE

### Architecture Overview

```
User Query
    │
    ▼
search_code_tool.py          ← LLM-facing tool interface (top_k: default=2, max=5)
    │
    ▼
HybridRetriever             ← Orchestrates 3-stage retrieval strategy
    │
    ├──► Stage 1: SQLite FTS5 MATCH       (fast tokenized search)
    │
    ├──► Stage 2: BM25Okapi scoring      (proper TF-IDF ranking)
    │
    └──► Stage 3: RapidFuzz fuzzy match  (typos, partial names, rephrasing)
    │
    ▼
Truncation: If source_code > 50 lines → truncate + add read_file hint
```

### Step-by-Step Flow

#### 1. LLM calls `search_code(query, top_k=2)`

The tool is defined in `src/liteagent/tools/search_code_tool.py`. Parameters:

| Parameter | Default | Max | Description |
|---|---|---|---|
| `query` | required | — | The search query, concept, or logic to look for |
| `top_k` | `2` | `5` | Maximum number of results to return |

The tool clamps `top_k` to 1–5 and delegates to `providers.insight.retriever.search(query, top_k)`.

#### 2. HybridRetriever.search() — Stage 1: FTS5 Tokenized Search

```python
# retriever.py
fts_query = " ".join(tokenize(query))  # e.g., "ValidateToken logic"
cursor.execute("""
    SELECT s.file_path, s.name, s.class_name, s.source_code, s.start_line, s.end_line
    FROM symbols s
    JOIN symbols_fts fts ON s.id = fts.rowid
    WHERE symbols_fts MATCH ?
    ORDER BY rank
    LIMIT ?
""", (fts_query, top_k))
```

- The query is tokenized into lowercase alphanumeric tokens.
- FTS5 performs fast tokenized search with built-in ranking (`ORDER BY rank`).
- FTS5 is kept in sync with the `symbols` table via SQLite triggers (insert/update/delete).
- If results are found, Stages 2 and 3 are skipped.

#### 3. HybridRetriever.search() — Stage 2: BM25 Scoring

```python
from rank_bm25 import BM25Okapi

# Build index lazily from all symbols in SQLite
corpus = [tokenize(f"{name} {class_name} {source_code}") for each symbol]
bm25 = BM25Okapi(corpus)

# Score the query
scores = bm25.get_scores(tokenize(query))
# Return top_k by score
```

- BM25 provides proper TF-IDF ranking — a query like `"token validation"` ranks `ValidateToken` higher than `GenerateToken`.
- The index is built lazily on first search and cached. It rebuilds when `mark_stale()` is called (triggered by watchdog file changes).
- Corpus document = `"{name} {class_name} {source_code}"`, tokenized by splitting on non-alphanumeric chars.
- If results are found, Stage 3 is skipped.

#### 4. HybridRetriever.search() — Stage 3: RapidFuzz Fuzzy Match

```python
from rapidfuzz import fuzz

name_score = fuzz.partial_ratio(query_lower, name.lower())
class_score = fuzz.partial_ratio(query_lower, class_name.lower())
best_score = max(name_score, class_score)
if best_score >= 65:  # threshold
    # include in results
```

- Handles typos, partial names, and rephrasing.
- Scores against both `name` and `class_name`, takes the best.
- Uses `partial_ratio` which finds the best matching substring.
- Results sorted by score descending.

#### 5. Source Code Truncation

After getting results, if a result's source code exceeds `MAX_SOURCE_LINES` (default: 50), it gets truncated:

```python
MAX_SOURCE_LINES = 50  # Easy to change

# If source_code has more than 50 lines:
truncated = "\n".join(lines[:50])
truncated += "\n// ... (Function/class line range 1-187. Use the read_file tool to read the whole thing)"
```

#### 6. Result Formatting

The tool formats results as:

**Short result (≤ 50 lines):**
```
File: D:\project\AuthService.cs
Class: AuthService
Code:
public bool ValidateToken(string token) {
    // ... full source ...
}
---
```

**Long result (> 50 lines, truncated):**
```
File: D:\project\AuthService.cs
Class: AuthService
Code:
public class AuthService {
    private readonly ITokenProvider _provider;
    // ... first 50 lines ...
    // ... (Function/class line range 1-187. Use the read_file tool to read the whole thing)
}
---
```

### Indexing Pipeline (How Code Gets Into SQLite)

The `ASTParser` (`src/liteagent/insight/indexer/ast_parser.py`) handles indexing:

1. **On startup**, `InsightProviders` spawns a background thread to parse the project directory.
2. **On file change**, `watchdog` triggers re-indexing of the modified file and marks the BM25 index as stale.
3. For each `.cs` file, tree-sitter parses the AST and extracts:
   - **Classes** → stored in SQLite `symbols` table
   - **Methods** → stored in SQLite `symbols` table (with `class_name` reference)
4. For non-`.cs` files (`.json`, `.config`, etc.), the entire file content is indexed as a single "File" symbol.
5. FTS5 virtual table stays in sync automatically via SQLite triggers.

### Key Files

| File | Role |
|---|---|
| `src/liteagent/tools/search_code_tool.py` | LLM-facing tool interface (top_k: default 2, max 5) |
| `src/liteagent/insight/retrieval/retriever.py` | `HybridRetriever` — 3-stage pipeline (FTS5 → BM25 → RapidFuzz) + truncation |
| `src/liteagent/insight/indexer/ast_parser.py` | Tree-sitter parsing → SQLite only |
| `src/liteagent/insight/indexer/graph_store.py` | SQLite `KnowledgeGraph` — symbols, relationships, FTS5 |
| `src/liteagent/insight/providers.py` | Wires everything together (no ChromaDB) |

---

## 2. Search Logs Tool

### Current Status: ✅ ACTIVE

### Architecture Overview

```
User Query
    │
    ▼
search_logs_tool.py          ← LLM-facing tool interface
    │
    ▼
LogIndex.search()            ← 3-stage pipeline on raw files
    │
    ├──► Stage 1: Case-insensitive exact match    (fast, zero deps)
    │
    ├──► Stage 2: Regex match                     (when is_plain=False)
    │
    └──► Stage 3: RapidFuzz partial_ratio          (handles typos, partial names)
```

### Step-by-Step Flow

#### 1. LLM calls `search_logs(query, is_plain, context_lines, last_hours, limit)`

The tool is defined in `src/liteagent/tools/search_logs_tool.py`. Parameters:

| Parameter | Default | Max | Description |
|---|---|---|---|
| `query` | required | — | Search term or pattern |
| `is_plain` | `True` | — | `True` = keyword, `False` = regex |
| `context_lines` | `2` | `5` | Surrounding lines to include |
| `last_hours` | `None` | — | Filter to last N hours (currently unused) |
| `limit` | `1` | `5` | Max results to return |

The tool enforces constraints (clamping `limit` to 1–5, `context_lines` to 0–5) and delegates to `providers.insight.log_index.search()`.

#### 2. LogIndex.search() — Raw File Scanning

The `search()` method iterates over log file paths configured in `settings.insight_log_paths`. For each file:

1. Opens the file and reads all lines into memory.
2. Calls `_match_lines()` to find matching line indices.
3. For each match, extracts context (surrounding lines) and formats the result.

#### 3. _match_lines() — 3-Stage Pipeline

This is the core matching logic. Stages run in order and **short-circuit** — if a stage produces results, later stages are skipped.

**Stage 1 — Case-insensitive exact match:**
```python
hits = [(i, False) for i, line in enumerate(lines) if query_lower in line.lower()]
```
- Fast, zero dependencies.
- Handles casing mismatches (e.g., `"functionA"` finds `"FunctionA"`).

**Stage 2 — Regex match (only when `is_plain=False`):**
```python
hits = [(i, False) for i, line in enumerate(lines)
        if re.search(query, line, re.IGNORECASE)]
```
- Supports complex patterns like `"Error [0-9]{3}"`.
- Wrapped in try/except to handle invalid regex gracefully.

**Stage 3 — RapidFuzz fuzzy match:**
```python
from rapidfuzz import fuzz
score = fuzz.partial_ratio(query_lower, line.lower())
if score >= 70:  # threshold
    scored.append((score, i))
```
- Handles typos, partial names, rephrasing, and extra words.
- Uses `partial_ratio` which finds the best matching substring within the line.
- Results are sorted by score (descending) and flagged as `fuzzy=True`.

#### 4. Result Ordering

- **Stage 1 & 2 hits:** Sorted by line number descending (newest first, assuming logs are chronological).
- **Stage 3 hits:** Sorted by fuzzy score descending (most relevant first).

#### 5. Context Extraction

For each matched line, the tool extracts surrounding lines:

```python
start_idx = max(0, i - context_lines)
end_idx = min(total_lines, i + context_lines + 1)
```

The matched line is prefixed with `>> ` and context lines with `   `:
```
   42: [INFO] Service started
>> 43: [ERROR] Connection reset by peer
   44: [INFO] Retrying...
```

#### 6. Result Formatting

The tool formats each result as:
```
[2026-05-24T18:00:00Z] ERROR - Line 43 - app.log [fuzzy match]
Context:
   42: [INFO] Service started
>> 43: [ERROR] Connection reset by peer
   44: [INFO] Retrying...
---
```

The `[fuzzy match]` label is appended when the result came from Stage 3, letting the LLM know the match may not be exact.

### FTS5 Indexed Search (Separate Path)

The `LogIndex` also has a `search_indexed()` method that uses SQLite FTS5 for searching ingested log records. Falls back to `LIKE` on FTS5 syntax errors. **This method is not called by the `search_logs` tool** — it exists as a separate API for ingested records.

### Key Files

| File | Role |
|---|---|
| `src/liteagent/tools/search_logs_tool.py` | LLM-facing tool interface with constraint enforcement |
| `src/liteagent/insight/logs/log_index.py` | `LogIndex` — 3-stage matching pipeline + FTS5 indexed search |
| `src/liteagent/insight/providers.py` | Creates `LogIndex` instance at `insight_dir / "log_index.db"` |

---

## Comparison: Search Code vs Search Logs

| Aspect | Search Code | Search Logs |
|---|---|---|
| **Status** | ✅ Active | ✅ Active |
| **Stage 1** | FTS5 tokenized search | Case-insensitive exact match |
| **Stage 2** | BM25Okapi (TF-IDF ranking) | Regex match |
| **Stage 3** | RapidFuzz fuzzy (threshold 65) | RapidFuzz fuzzy (threshold 70) |
| **Data Source** | SQLite `knowledge.db` (symbols + FTS5) | Raw `.log` files + SQLite `log_index.db` |
| **Indexing** | Background AST parsing → SQLite | None (reads files on-the-fly) |
| **Real-time Sync** | Watchdog → re-parse + mark BM25 stale | None (reads current file state) |
| **Result Format** | File + Class + Code (truncated at 50 lines) | Timestamp + Level + Line + Context Block |
| **Max Results** | `top_k` (default 2, max 5) | `limit` (default 1, max 5) |
| **Fuzzy Matching** | Yes (RapidFuzz, threshold 65) | Yes (RapidFuzz, threshold 70) |
| **BM25 Used** | ✅ Yes (rank-bm25) | No |
| **ChromaDB Used** | No (removed) | No |

---

## Configurable Constants

| Constant | File | Default | Description |
|---|---|---|---|
| `MAX_SOURCE_LINES` | `retriever.py` | `50` | Max lines of source code before truncation |
| `MAX_TOP_K` | `search_code_tool.py` | `5` | Maximum results for search_code |
| `DEFAULT_TOP_K` | `search_code_tool.py` | `2` | Default results for search_code |

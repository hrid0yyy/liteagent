# Log Tools Upgrade Plan

## Overview
1. **New tool: `extract_log_patterns`** — Scans C# source for logging calls, extracts message templates
2. **Upgrade `search_logs`** — Pure Python with pre-search verification
3. **Upgrade `read_log_lineRange`** — Streaming line reads instead of loading entire file
4. **Pre-search verification** — Validate queries against extracted patterns before searching
5. **Cleanup** — Remove unused SQLite FTS5 code

---

## 1. Tool: `extract_log_patterns`

**Agent-facing tool** — queries the knowledge graph (already populated by the AST parser) to show all log message templates, grouped by file and method.

### No parameters needed
The AST parser (tree-sitter) already extracts log templates at startup and stores them in the `log_templates` SQL table. This tool just queries that data.

### Data Source
- **`log_templates` table** — `file_path`, `method_name`, `level`, `template` (populated by AST parser)
- **`symbols` table** — method `name`, `start_line`, `end_line`, `class_name` (for line ranges)

### Output Format
```
Found 23 log patterns in 8 files:

C:/project/src/Services/OrderService.cs
  ProcessOrder() [lines 80-120]
    INFO: "Processing order {...}"
    INFO: "Order {...} completed successfully"
  LogError() [lines 130-140]
    ERROR: "Payment failed for invoice {...}"

C:/project/src/App.xaml.cs
  Application_Startup() [lines 20-50]
    INFO: "[APP] Application startup initiated"
    INFO: "[APP] Command line args: {...}"
  [Outside method]
    INFO: "[APP] Top-level log"
```

### Template Conversion
The AST parser stores templates as regex patterns (e.g., `\[APP\] Command line args: (.*?)`). The tool converts these back to readable format:
- `(.*?)` → `{...}`
- `\[` → `[`, `\]` → `]`, etc.

### Side Effect
Readable messages are stored in `LogIndex._known_log_messages` for the pre-search verification step.

---

## 2. Upgrade `search_logs` → Pure Python with Streaming

Consistent with `search_in_files` tool — pure Python, no external dependencies.

### Search Flow

```
search_logs(query)
  │
  ├─ Step 1: Pre-search verification
  │   Check query against extracted log patterns
  │   If no match → return "No logging call matches this query"
  │
  ├─ Step 2: Stream-based search
  │   Stage 1 (plain): case-insensitive substring match, line by line
  │   Stage 2 (regex): regex match, line by line
  │   Stage 3 (fuzzy): RapidFuzz partial_ratio fallback
  │
  └─ All stages stream the file line by line (no readlines())
```

### Streaming Approach

Instead of loading the entire file into memory with `readlines()`, stream line by line:

```python
def search(self, query, is_plain=True, context_lines=2, last_hours=None, limit=1):
    results = []
    for path_str in settings.insight_log_paths:
        log_file = Path(path_str)
        if not log_file.exists():
            continue
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = list(f)  # Still need all lines for context, but streamed read
                total_lines = len(lines)
                matched = self._match_lines(lines, query, is_plain)
                # ... build results with context ...
        except Exception:
            pass
    return results[:limit]
```

**Note:** For context lines, we still need surrounding lines. The streaming improvement is primarily in `read_log_lineRange` (which only needs a small range). For `search_logs`, the 3-stage matching already works well — the main improvement is the pre-search verification step that avoids unnecessary file reads entirely.

---

## 3. Upgrade `read_log_lineRange` → Streaming

### Current (loads entire file)
```python
raw_content = file_path.read_text(encoding="utf-8")
lines = raw_content.splitlines()
selected_lines = lines[start_idx:end_idx]
```

### New (streams only needed lines)
```python
from itertools import islice

with open(path, "r", encoding="utf-8", errors="ignore") as f:
    selected = list(islice(f, start_idx, start_idx + range))
```

Only reads the needed lines into memory, not the entire file.

---

## 4. Pre-Search Verification with Force Parameter

Before running rg/Python search, check if the query could possibly match any extracted log pattern.

### `force` Parameter on `search_logs`
- `force` (bool, default `false`): Bypass pre-search verification
- `force=false` → verification runs normally (default)
- `force=true` → skip verification, execute search directly

### Smart Verification Logic

```python
def _verify_query(self, query: str) -> bool:
    """Check if query could possibly match any known log pattern."""
    if not self._known_log_messages:
        return True  # No patterns extracted yet, allow all
    
    query_lower = query.lower()
    
    for template in self._known_log_messages:
        # Strip template params: "Processing order {...}" → "Processing order "
        stripped = re.sub(r'\{[^}]+\}', '', template).strip().lower()
        
        # Exact substring match
        if stripped and stripped in query_lower:
            return True
        if query_lower in stripped:
            return True
        
        # Keyword overlap: any word from query appears in template
        query_words = set(query_lower.split())
        template_words = set(stripped.split())
        if query_words & template_words:
            return True

        # Partial word match: "app" is a substring of "appdomain"
        # Only check if query word is substring of template word (not reverse)
        for q_word in query_words:
            for t_word in template_words:
                if len(q_word) >= 3 and q_word in t_word:
                    return True
    
    return False
```

### Examples

| Call | Result |
|---|---|
| `search_logs("Processing order 145")` | Verification passes (matches template) → search runs |
| `search_logs("order")` | Verification passes (substring of template) → search runs |
| `search_logs("app domain")` | Verification passes ("app" is substring of "appdomain") → search runs |
| `search_logs("145")` | Verification fails → blocked |
| `search_logs("145", force=true)` | Bypasses verification → search runs |
| `search_logs("banana")` | Verification fails → blocked |
| `search_logs("banana", force=true)` | Bypasses verification → search runs |

### Early Rejection Response (force=false)
```
"No logging call in the codebase matches this query. The searched term cannot appear in log files. Use force=true to search anyway."
```

### When Verification Is Skipped
- If `extract_log_patterns` has not been called yet (no known messages) → skip verification, proceed to search
- If `is_plain=False` (regex query) → skip verification, regex is hard to validate against templates
- If `force=true` → skip verification, execute search directly

---

## 5. Cleanup

Remove unused SQLite FTS5 code from `log_index.py`:
- `_init_db()` method
- `search_indexed()` method
- `get_recent_errors()` method
- `db_path` parameter from `__init__`
- All SQLite/FTS5 related code

---

## Files to Create/Modify

| File | Change |
|---|---|
| `tools/extract_log_patterns_tool.py` | **NEW** — extract_log_patterns tool |
| `tools/factory.py` | Register new tool |
| `tools/registry.py` | Add sample inputs for extract_log_patterns |
| `insight/logs/log_index.py` | Add verification, add _known_log_messages, remove SQLite |
| `tools/search_logs_tool.py` | Minor updates if needed |
| `tools/read_log_lineRange_tool.py` | Use islice streaming |

## Todos
1. Create `extract_log_patterns` tool with C# logging regex patterns
2. Register in `factory.py` and add sample inputs in `registry.py`
3. Add pre-search verification to `LogIndex` using extracted patterns
4. Add `force` parameter to `search_logs` tool
5. Update `read_log_lineRange` to use streaming (`islice`)
6. Remove SQLite FTS5 code from `log_index.py`
7. Unit tests

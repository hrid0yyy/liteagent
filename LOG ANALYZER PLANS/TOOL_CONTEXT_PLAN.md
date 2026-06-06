# Plan

## Problem
Two guardrails needed:

### Guardrail 1: Prevent Redundant Tool Calls
Prevent redundant tool calls across a session (no per-turn reset) for:
- `read_file`, `list_files`, `get_workspace_info`, `read_log_lineRange`, `search_logs`

If the same tool is called with the same args and the output is likely still in the LLM's context, block the call and return "This tool output is already in your context."

### Guardrail 2: Log File Access Restriction
Only `read_log_lineRange` and `search_logs` may access log files. All other tools (e.g., `read_file`, `write_file`, `modify_file`, `search_in_files`, `delete_path`, `rename_path`) must be blocked from operating on any configured log path.

---

## Guardrail 1: Distance-Based Tool Tracker

### Core Idea
Track how many tool calls have happened *since* the last call with the same args. If enough tool calls have passed, the output is likely evicted from the LLM's context window → allow re-execution.

### How It Works
- Maintain a global `tool_call_counter` that increments on every tool call.
- For each key `(tool_name + normalized_args)`, store the counter value when it was last called.
- On a new call:
  - If key exists AND `current_counter - last_call_counter <= THRESHOLD` → **block** (output likely still in context)
  - If key not in tracker OR `current_counter - last_call_counter > THRESHOLD` → **allow** (output likely evicted from context)
- On execution → store `current_counter` as the value for the key.

### Why No `force` Parameter
The distance-based expiry makes `force` unnecessary:
- Recent duplicate → blocked automatically (output still in context)
- Old duplicate → allowed automatically (output likely evicted)
- No manual override needed — the system handles both cases naturally.

### Why No Fingerprint Checks
- For file tools (`read_file`, `list_files`, `get_workspace_info`): Even if the agent changed the file, it already knows what it wrote → skip duplicate.
- For log tools (`read_log_lineRange`, `search_logs`): Agent can't modify logs → skip duplicate.
- Pure duplicate detection is sufficient. No mtime/size fingerprint needed.

### Auto-Compact Compatibility (Future)
When auto-compact runs, it will compact/remove tool outputs from the context. The tracker should **clear all entries** on auto-compact:
```python
def on_auto_compact(self):
    """Called when auto-compact runs. Clears all tracker entries."""
    self._entries.clear()
```
This is simpler than selective invalidation and safe because after compaction we can't be sure which outputs are still in full context.

### Data Model

| Component | Detail |
|---|---|
| **Name** | `tool_tracker` (dict in agent state) |
| **Key** | `tool_name + normalized_args` |
| **Value** | `{ last_call_counter: int }` |
| **Global counter** | `tool_call_counter` — increments on every tool call |
| **Guarded tools** | `read_file`, `list_files`, `get_workspace_info`, `read_log_lineRange`, `search_logs` |
| **Block condition** | Key exists AND `current_counter - last_call_counter <= THRESHOLD` |
| **Allow condition** | Key not in tracker OR distance > THRESHOLD |
| **Block response** | `"This tool output is already in your context."` |
| **On execution** | Store `current_counter` for the key |
| **Auto-compact** | `on_auto_compact()` → clear all entries |
| **THRESHOLD** | Configurable (e.g., 15-20) |
| **Lifecycle** | Session-scoped, resets on new session |

---

## Guardrail 2: Log File Access Restriction

### Core Idea
Log files are read-only system artifacts. The agent must never modify, delete, rename, or read them with general-purpose tools. Only the dedicated log tools (`read_log_lineRange`, `search_logs`) may access them.

### How Log Tools Work
- `search_logs`: Searches all configured log paths from `settings.insight_log_paths`. No file path argument — it always searches all configured logs.
- `read_log_lineRange`: Takes a `path` arg to read a specific log file by line range. This is the only way to read log file content directly.

### Restricted Tools
The following tools must be blocked if their target path matches a configured log path:
- `read_file` (file_path arg)
- `write_file` (file_path arg)
- `modify_file` (file_path arg)
- `search_in_files` (dir_path arg — if it covers a log directory)
- `delete_path` (path_to_delete arg)
- `rename_path` (old_path arg)
- `list_files` (dir_path arg — if it covers a log directory)

### How It Works
- On each non-log tool call, extract the target path from the tool's args.
- Resolve the target path to an absolute path.
- Compare against resolved `settings.insight_log_paths`.
- If the target path is a log file OR is inside a log directory → **block**.
- Block response: `"Log files can only be accessed through read_log_lineRange or search_logs tools."`

### Path Matching Logic
```python
def is_log_path(self, target_path: str) -> bool:
    """Check if a path matches any configured log path."""
    resolved = Path(target_path).resolve()
    for log_path_str in settings.insight_log_paths:
        log_resolved = Path(log_path_str).resolve()
        # Exact match (file) or parent match (directory)
        if resolved == log_resolved or log_resolved in resolved.parents:
            return True
    return False
```

---

## Code Organization

### New File: `core/tool_tracker.py`
Separate from existing `core/read_tracker.py` (which tracks file content freshness). The new `ToolTracker` class handles both guardrails: call-level duplicate prevention and log file access restriction.

```python
class ToolTracker:
    # Guardrail 1: Duplicate prevention
    GUARDED_TOOLS = {"read_file", "list_files", "get_workspace_info",
                     "read_log_lineRange", "search_logs"}

    # Guardrail 2: Log file access — only these tools may touch log paths
    LOG_TOOLS = {"read_log_lineRange", "search_logs"}

    # Tools that take a path arg which could target a log file
    PATH_ARG_TOOLS = {
        "read_file": "file_path",
        "write_file": "file_path",
        "modify_file": "file_path",
        "delete_path": "path_to_delete",
        "rename_path": "old_path",
        "search_in_files": "dir_path",
        "list_files": "dir_path",
    }

    def __init__(self, threshold: int = 15):
        self._entries: Dict[str, int] = {}  # key → last_call_counter
        self._call_counter: int = 0
        self._threshold = threshold

    # --- Guardrail 1: Duplicate Prevention ---

    def _make_key(self, tool_name: str, args: dict) -> str:
        """Build a normalized key from tool name + sorted args."""

    def should_block(self, tool_name: str, args: dict) -> bool:
        """Check if this call should be blocked (duplicate within threshold)."""

    def record_call(self, tool_name: str, args: dict) -> None:
        """Record that a tool call was made (store current counter)."""

    def increment_counter(self) -> None:
        """Increment the global call counter (called on EVERY tool call)."""

    def on_auto_compact(self) -> None:
        """Clear all entries when auto-compact runs (future use)."""

    # --- Guardrail 2: Log File Access ---

    def is_log_path(self, target_path: str) -> bool:
        """Check if a path matches any configured log path."""

    def should_block_log_access(self, tool_name: str, args: dict) -> bool:
        """Check if a non-log tool is trying to access a log file."""
```

### Modified: `core/state.py`
Add `tool_tracker` dict and `tool_call_counter` int to `AppState`.

### Modified: `core/container.py`
Instantiate `ToolTracker` and expose it via `get_container()`.

### Modified: `graph/nodes/executor.py`
Two guardrail checks in the tool call loop:

```python
# Inside the tool call loop, after validation and before execution:
tool_tracker = get_container().tool_tracker

# Guardrail 2: Log file access (check FIRST — hard block, no distance logic)
if tool_name in ToolTracker.PATH_ARG_TOOLS:
    if tool_tracker.should_block_log_access(tool_name, typed_args):
        outputs.append({
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "output": "Log files can only be accessed through read_log_lineRange or search_logs tools.",
            "diffs": [],
        })
        log_event("tool_log_access_blocked", "executor", ...)
        continue

# Guardrail 1: Duplicate prevention
tool_tracker.increment_counter()

if tool_name in ToolTracker.GUARDED_TOOLS:
    if tool_tracker.should_block(tool_name, typed_args):
        outputs.append({
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "output": "This tool output is already in your context.",
            "diffs": [],
        })
        log_event("tool_tracker_blocked", "executor", ...)
        continue

# ... execute tool normally ...

# After successful execution of a guarded tool:
if tool_name in ToolTracker.GUARDED_TOOLS:
    tool_tracker.record_call(tool_name, typed_args)
```

## Todos
1. Create `core/tool_tracker.py` with the `ToolTracker` class (both guardrails).
2. Add `tool_tracker` dict and `tool_call_counter` int to `AppState` in `core/state.py`.
3. Instantiate `ToolTracker` in `core/container.py` and expose via `get_container()`.
4. Integrate both guardrail checks into `graph/nodes/executor.py`.
5. Update logging to surface tracker blocks and log access blocks.
6. Add/adjust unit tests to cover:
   - Duplicate block logic and distance-based expiry
   - Log file access restriction for each restricted tool

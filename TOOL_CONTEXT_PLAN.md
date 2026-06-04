# Plan

## Problem
Prevent redundant tool calls across a session (no per-turn reset) for:
- `read_file`, `list_files`, `get_workspace_info`, `read_log_lineRange`, `search_logs`

If the target file/dir/logs are unchanged (mtime + size fingerprint) and the tool arguments are identical, the tool call should be blocked and return a message like “this tool output is already in your context.”

## Approach
- Add a session-scoped cache in agent state to remember prior tool calls and the last observed source fingerprint for each (tool name + normalized args).
- Compute a lightweight source fingerprint (mtime + size) for each tool target before execution; compare to the cached fingerprint to decide whether to block.
- Implement the guard in the executor so the tool is not invoked when unchanged; emit a consistent “already in context” response and log the block.
- Keep the cache across user turns; only reset on new session.

## Todos
1. Extend `core/state.py` and CLI state initialization with a session-scoped `tool_context_cache` and store the project dir for path resolution.
2. Add executor helpers to normalize tool arguments and compute mtime+size fingerprints for files, dirs, and configured log paths.
3. In `executor.py`, short-circuit the guarded tools when the cached fingerprint matches the current fingerprint, and return a friendly “already in context” message.
4. Update logging to surface guardrail blocks and preserve maintainability.
5. Add/adjust unit tests to cover the no-change block for at least one file tool and one log tool.

## Notes
- Cache is keyed by tool name + normalized args (per your requirement).
- For `search_logs`, allow execution if any configured log file changed.
- Missing files or invalid paths should fall through to the tool’s normal error handling (no cache write).

# Insight Tools Testing Plan

This document outlines the strategy for testing the 6 Insight tools using the `CodeShareTest` project.

## 1. Setup
The test project is a .NET Console application located in `tests/test-project/CodeShareTest`.
- **Logs Location:** `C:\temp\codeshare-logs\app.log`
- **Log Rate:** ~10 entries per second.
- **Errors:** Randomized database connection errors and loop exceptions.

## 2. Test Cases for Insight Tools

### Tool 1: `search_code`
**Goal:** Verify the agent can find specific logic in the .NET code.
- **Input:** `query="ValidateToken logic"`
- **Expected:** Should return the `AuthService.ValidateToken` method.
- **Input:** `query="how are logs being spammed"`
- **Expected:** Should return the `LogSpammer` class implementation.

### Tool 2: `trace_calls`
**Goal:** Verify AST traversal and relationship mapping.
- **Input:** `symbol="ProcessNextBatch"`, `direction="both"`
- **Expected:** 
  - Callers: `Main`
  - Callees: `ValidateToken`, `SaveData`

### Tool 3: `get_project_map`
**Goal:** Verify directory structure overview.
- **Input:** `path="tests/test-project"`
- **Expected:** List the `CodeShareTest` folder and its contents.

### Tool 4: `search_logs`
**Goal:** Verify FTS5 indexing and high-volume retrieval.
- **Input:** `query="Connection reset"`, `is_plain=true`
- **Expected:** List multiple occurrences of the random error injected by the spammer.

### Tool 5: `get_log_errors`
**Goal:** Verify error aggregation and statistics.
- **Input:** `path="C:/temp/codeshare-logs/app.log"`, `last_hours=1`
- **Expected:** A JSON summary showing the count of "Connection reset" and "Main loop exception" errors.

### Tool 6: `trace_error_to_code`
**Goal:** Verify the link between logs and source code.
- **Input:** `error_string="Database write failed due to corrupted data"`
- **Expected:** Point directly to `DatabaseService.SaveData` in `Program.cs`.

## 3. Execution
1. Open the Tool Inspector (`liteagent chat -i`).
2. Run the .NET project in a separate terminal: `cd tests/test-project/CodeShareTest && dotnet run`.
3. Use the Tool Inspector to execute the inputs above.

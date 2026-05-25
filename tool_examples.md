# LiteAgent Diagnostic Tools - Sample Usage Guide
This document provides sample inputs and expected outputs for the 5 core diagnostic tools, tested against the `CodeShareTest` test project.

## 1. `search_code`
Searches the codebase for specific functionality, concepts, or logic.

**Example 1:**
- **Input:** `query="ValidateToken logic"`, `top_k=3`
- **Expected Output:** Returns a JSON structure containing the `AuthService` class, the `ValidateToken` method, and the C# source code snippet implementing it.

**Example 2:**
- **Input:** `query="net8.0"`, `top_k=3`
- **Expected Output:** Returns a match inside `CodeShareTest.csproj` highlighting the `<TargetFramework>net8.0</TargetFramework>` node.

---

## 2. `trace_calls`
Traces the execution flow of a specific function or class.

**Example 1 (Callers):**
- **Input:** `symbol="ValidateToken"`, `direction="callers"`, `depth=3`
- **Expected Output:** A JSON tree representing the call graph, showing that `ProcessNextBatch` (and ultimately `Main`) relies on `ValidateToken`.

**Example 2 (Callees):**
- **Input:** `symbol="ProcessNextBatch"`, `direction="callees"`, `depth=1`
- **Expected Output:** A JSON tree showing that `ProcessNextBatch` actively calls `ValidateToken` and `SaveData`.

---

## 3. `search_logs`
Searches through application log files for errors, keywords, or patterns.

**Example 1:**
- **Input:** `query="Connection reset"`, `is_plain=True`
- **Expected Output:** Returns the exact log lines such as `[2026-05-24T18:00:01Z] [ERROR] Connection reset by peer in DatabaseService` along with surrounding context.

**Example 2:**
- **Input:** `query="bootloader initialized"`, `is_plain=True`
- **Expected Output:** Returns the critical startup log `[FATAL] Critical system bootloader initialized (AppVersion v1.0.0)`.

---

## 4. `get_log_stats`
Analyzes log frequencies to identify spammy logs or recurring issues by grouping them by their source template.

**Example 1 (Filter by Level):**
- **Input:** `level="ERROR"`
- **Expected Output:** A statistical summary of all `ERROR` logs mapped to their exact source templates (e.g., showing how many times the Connection Reset template fired in `Program.cs`'s `Start` method).

**Example 2 (Filter by Module):**
- **Input:** `module="Program.cs"`
- **Expected Output:** A summary of all log frequencies (WARN, ERROR, FATAL, etc.) originating purely from the `Program.cs` file.

---

## 5. `trace_log_to_code`
Finds the exact source code location that generated a specific log message.

**Example 1:**
- **Input:** `log_string="[2026-05-24T18:00:01Z] [ERROR] Connection reset by peer in DatabaseService"`
- **Expected Output:** Directly returns `File: Program.cs`, `Method: Start`, and prints out the exact lines of C# source code where the logger was called.

**Example 2:**
- **Input:** `log_string="[2026-05-24T18:05:00Z] [WARN] Background sync delayed due to high latency"`
- **Expected Output:** Traces back perfectly to the exact `Start` method warning invocation and returns the source code block.

# `trace_log_to_code` Tool Implementation Plan

## Overview
Currently, when the agent finds a relevant log line using `search_logs`, it has to guess or run secondary code searches to figure out which file and method actually generated that log. 

To bridge this gap instantly, we will create a dedicated tool: `trace_log_to_code`. This tool will leverage the highly structured `.liteagent/logbase.json` to reverse-map a raw log string back to its exact source code location.

## 1. Tool Signature
**Name:** `trace_log_to_code`
**Description:** Takes a raw log string from the runtime logs and returns the exact source code method(s) that emitted it, including the file path and line numbers.
**Parameters:**
- `log_line` (str): The specific log message string (or a significant chunk of it) found in the runtime logs.

## 2. Execution Mechanism
We already have all the data we need inside `logbase.json`, which maps `Filepath -> Class -> Method -> {log_lines, line_range}`.

### A. Data Loading
- The tool reads `.liteagent/logbase.json`.
- It flattens the hierarchy to easily iterate over every single method and its associated `log_lines` array.

### B. Fuzzy Matching (The Core Logic)
Because runtime logs often contain dynamic variables (e.g., `"User 1234 connected"` while the code says `"User {id} connected"`), exact string matching will fail.
- We will use the `rapidfuzz` library (already installed and used by our `HybridRetriever`).
- For every method, we compare the input `log_line` against every string in its `log_lines` array using `fuzz.partial_ratio` or `fuzz.token_set_ratio`.
- We record the highest similarity score for that method.

### C. Ranking and Selection
- Sort all methods based on their highest fuzzy similarity score.
- **Best Match:** The method with the highest score (usually >= 85%).
- **Other Potential Matches:** Any other methods that scored above a reasonable safety threshold (e.g., >= 65%), in case the log string is generic (like `"Connection failed."`).

## 3. Output Format
The tool will return a structured, highly readable response for the agent:

```text
[BEST MATCH] (Score: 95%)
File: src/Network/DiscoveryService.cs
Class: DiscoveryService
Method: StartAdvertising
Line Range: 36-70
Matched Template: "mDNS Advertising started for user: {user_id}"

[OTHER POTENTIAL MATCHES]
1. (Score: 72%)
File: src/Network/FallbackService.cs
Class: FallbackService
Method: StartAsync
Line Range: 22-34
Matched Template: "Failed to start initial mDNS advertising."
```

## 4. Integration
- The tool will be placed in `src/liteagent/tools/trace_log_to_code_tool.py`.
- It will be added to the restricted toolset provided to the **Diagnostic Sub-Agent** during the `/analyze` command.
- When the sub-agent finds an error in the logs (using `search_logs`), its immediate next step will be calling `trace_log_to_code` on that error string to instantly jump to the broken code.

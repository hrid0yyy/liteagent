# `trace_method_workflows` Tool Implementation Plan

## Overview
Once the agent knows exactly which method threw an error (thanks to `trace_log_to_code`), the next logical question is: *"How did the application get there?"* 

To answer this, we will build the `trace_method_workflows` tool. This tool will take a specific method name and query the `liteagent` Knowledge Graph (the SQLite `relationships` table) to reconstruct the execution flow, showing all upstream callers (how it was invoked) and downstream callees (what it invokes).

## 1. Tool Signature
**Name:** `trace_method_workflows`
**Description:** Takes a specific method or class name and returns its complete execution context, showing its upstream callers (the workflow that led to it) and downstream dependencies.
**Parameters:**
- `target_name` (str): The exact name of the method or class to trace (e.g., `StartAdvertising` or `DiscoveryService.StartAdvertising`).
- `direction` (str, optional): `"upstream"` (show callers), `"downstream"` (show callees), or `"both"`. Defaults to `"both"`.
- `max_depth` (int, optional): How far up/down the call stack to trace. Defaults to 2.

## 2. Execution Mechanism
The `liteagent` indexer (`graph_store.py`) already tracks code dependencies and stores them in the `relationships` table inside `.liteagent/insight/knowledge.db`.

### A. Resolution
- Since method names can be generic (e.g., `Run`), the tool will first query the `symbols` table to resolve the `target_name` to its fully qualified name (`qualified_name`).
- If multiple methods share the same name across different files, it will trace all of them but group the output by file.

### B. Upstream Traversal (Who calls this?)
- Using a recursive SQL query (or a Python loop), query the `relationships` table where `target = qualified_name`.
- This reveals the immediate parent method.
- Repeat the query for the parent method (up to `max_depth`) to build the full chain back to the application entry point (e.g., an HTTP handler or `Main` method).

### C. Downstream Traversal (What does this call?)
- Query the `relationships` table where `source = qualified_name`.
- This reveals all internal methods, utilities, or external APIs that this method relies on.

## 3. Output Format
The tool will return a visual, tree-like string structure that the agent can easily understand. If a method is called from multiple different places, **all separate execution flows** will be mapped out clearly:

```text
Tracing workflows for: DiscoveryService.StartAdvertising

▼ UPSTREAM WORKFLOWS (How it gets called):

  Flow 1 (App Startup):
  [Depth 2] Program.Main (src/Program.cs:15)
     └── [Depth 1] DiscoveryManager.InitializeNetwork (src/Network/Manager.cs:42)
            └── [TARGET] DiscoveryService.StartAdvertising

  Flow 2 (API Request):
  [Depth 2] AdminController.RestartNetworkEndpoint (src/Api/AdminController.cs:88)
     └── [Depth 1] DiscoveryManager.RestartService (src/Network/Manager.cs:105)
            └── [TARGET] DiscoveryService.StartAdvertising

▼ DOWNSTREAM DEPENDENCIES (What it calls):
  [TARGET] DiscoveryService.StartAdvertising
     ├── [Depth 1] Logger.LogInfo (src/Utils/Logger.cs:10)
     ├── [Depth 1] UdpClient.SendAsync (External/System)
     └── [Depth 1] NetworkUtils.GetLocalIpAddress (src/Utils/Network.cs:88)
```

## 4. Integration
- The tool will be placed in `src/liteagent/tools/trace_method_workflows_tool.py`.
- It will be added to the restricted toolset provided to the **Diagnostic Sub-Agent** during the `/analyze` command.
- **The Ultimate Diagnostic Trio:** 
  1. `search_logs`: Finds the error.
  2. `trace_log_to_code`: Finds the exact method that threw the error.
  3. `trace_method_workflows`: Finds out exactly what user action or API endpoint triggered that method.

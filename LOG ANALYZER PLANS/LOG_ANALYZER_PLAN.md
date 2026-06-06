# LogAnalyzer Pivot Plan

## Objective
Pivot the existing LiteAgent into a specialized **LogAnalyzer**. The new workflow will allow a user to provide an issue description and configure log files. The agent will then autonomously analyze the configured log files to find the root cause of the issue and suggest a solution.

## Core Features
1.  **Persistent Project Configuration**: Log paths and issue descriptions are saved to a local configuration file (`.liteagent/analyzer_config.json`) so they persist across sessions for a given project.
2.  **Interactive REPL Configuration**: Users configure the agent using fast, client-side slash commands directly in the chat interface. **No LLM calls are made for these configuration steps**, ensuring instant feedback.
3.  **Logbase Extraction Engine (Incremental & LLM-Powered)**:
    *   **Automated Pre-processing**: Runs automatically before `/analyze` or manually via `/extractlogs`.
    *   **LLM Descriptions**: For every method containing a log statement, an LLM generates a functional description of what that method does.
    *   **Real-time Progress Feedback**: During extraction, the terminal will show a live progress indicator (e.g., `[3/10] Generating description for process_payment()...`) so the user can track the status of LLM processing.
    *   **Persistence**: Extracted templates and descriptions are cached in `.liteagent/logbase.json`. The structure of this file must strictly follow this hierarchy:
        *   Grouped by **Filepath**.
        *   Grouped by **Class** within the file (or standalone functions).
        *   Grouped by **Method** within the class.
        *   Each method entry must contain:
            *   `log_lines`: An array of the log statements found in the method.
            *   `description`: The LLM-generated functional description of what the method does.
            *   `line_range`: The starting and ending line numbers of the method in the code file.
            *   **Sample JSON Structure**:
                ```json
                {
                  "src/payment/gateway.py": {
                    "PaymentProcessor": {
                      "process_payment": {
                        "log_lines": [
                          "logger.info('Processing payment for user %s')",
                          "logger.error('Payment failed due to invalid token')"
                        ],
                        "description": "Handles the core payment processing logic and error states.",
                        "line_range": [42, 85]
                      }
                    }
                  }
                }
                ```
    *   **Incremental Efficiency**: Uses method-level hashing to track changes. If a method is unmodified, it skips the LLM call and uses the cached description, significantly reducing latency and token costs.
4.  **Automated Log Ingestion**: Utilize the existing `LogDiscoverer` and `LogParser` to automatically parse and index the configured logs into SQLite FTS5.
5.  **Issue Analysis**: Given the configured issue and the enriched logbase context, the agent automatically formulates queries to search the indexed logs for relevant errors, anomalies, or stack traces when `/analyze` is called.
6.  **Root Cause & Solution Suggestion**: Synthesize the findings from the logs and the codebase to suggest a concrete solution to the user.

## Slash Commands (Client-Side / No LLM)
The chat interface will intercept these commands locally to update the persistent configuration:

*   `/addlog <file_path>`: Validates and adds a log file with a unique 4-char ID.
*   `/addissue <issue_description>`: Adds an issue description with a unique 4-char ID.
*   `/logs`: Displays a table of configured logs.
*   `/issues`: Displays a table of configured issues.
*   `/rmlog <id>` / `/rmissue <id>`: Removes a configuration entry.
*   `/editlog <id> <new_path>` / `/editissue <id> <new_description>`: Updates an entry.
*   `/renameid <old_id> <new_id>`: Customizes an ID.
*   `/extractlogs [--empty]`
    *   **Action**: Manually triggers the Logbase Extraction Engine.
    *   **Options**:
        *   `--empty`: Performs extraction and saves to `logbase.json` **without calling the LLM**. The description fields will be left empty, allowing for instant extraction or manual developer input.
    *   **Standard Behavior**: Without the flag, it scans for changes and uses the LLM to generate/update descriptions for modified code. (Also runs automatically before `/analyze`).
*   **Tool Inspector Integration**:
    *   The extraction functionality will be registered as system-level actions in the **Tool Inspector** web UI (`liteagent chat -i`).
    *   There will be two specific options available, **neither of which take any parameters**:
        1.  `extract-log-with-description`: Performs the full extraction using the LLM to generate descriptions.
        2.  `extract-log-empty`: Performs the fast extraction, leaving descriptions empty (bypassing the LLM).
    *   The Inspector UI will show the same real-time progress feedback as the CLI.

## AI Analysis Commands
*   `/analyze <issue_id> <log_id1> [log_id2] ...`
    *   **Action**: Triggers the main LLM analysis loop.
    *   **Parameters**: Exactly one issue ID and one or more log IDs.
    *   **Process**: 
        1.  Runs the **Logbase Extraction Engine** (incremental update).
        2.  Indexes the specified logs.
        3.  Injects the issue, log paths, and the enriched `logbase` context into the agent.
        4.  Starts the LangGraph analysis loop.

## Technical Changes Needed
1.  **Config Manager**: Handle `.liteagent/analyzer_config.json` for persistent IDs.
2.  **REPL Interceptor**: Handle all `/` commands in `src/liteagent/cli/main.py`.
3.  **Logbase Extractor**: Build `src/liteagent/insight/logs/logbase_extractor.py` with AST parsing, hashing, and LLM description generation logic.
4.  **System Prompt Injection**: Dynamically inject the issue and the enriched `logbase.json` content into the planner's context.
5.  **Tool Pruning**: **Remove** `src/liteagent/tools/extract_log_patterns_tool.py` as it is now an automated prerequisite.

## Verification
*   **Efficiency Test**: Run `/extractlogs` twice on an unmodified codebase; verify zero LLM calls on the second run.
*   **Incremental Test**: Modify one method and verify only that method is re-processed by the LLM.
*   **Diagnosis Test**: Verify the agent uses the logbase descriptions to accurately link log entries to functional code areas.

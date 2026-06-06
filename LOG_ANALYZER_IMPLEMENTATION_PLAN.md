# LogAnalyzer Implementation Plan

This document breaks down the `LOG_ANALYZER_PLAN.md` into actionable implementation steps.

## Phase 1: Configuration Management
**Goal:** Establish persistent storage for logs and issue configurations.
1. **Create Config Manager**: 
   - Implement logic to initialize, read, and update `.liteagent/analyzer_config.json`.
   - Define the schema for storing log paths and issue descriptions with their associated 4-character unique IDs.
   - Implement helper functions for adding, editing, removing, and renaming entries.

## Phase 2: Logbase Extraction Engine
**Goal:** Build the system that parses code for log statements, generates descriptions, and tracks changes.
1. **AST Parsing & Hashing**:
   - Create `src/liteagent/insight/logs/logbase_extractor.py`.
   - Implement AST parsing to identify all classes and methods in the codebase.
   - Implement method-level hashing to detect changes between runs.
   - Extract log statements and their corresponding `line_range` for each method.
2. **LLM Integration**:
   - Implement the LLM call to generate functional descriptions for methods containing logs.
   - Set up the real-time progress feedback in the terminal (e.g., `[3/10] Generating description for process_payment()...`).
3. **Persistence & Schema**:
   - Save the extraction results to `.liteagent/logbase.json` ensuring the strict hierarchical format: `Filepath` -> `Class` -> `Method` -> `{ log_lines, description, line_range }`.
4. **Incremental Efficiency**:
   - Wire up the hashing logic so that the LLM is only called for methods whose hash has changed since the last run.

## Phase 3: Client-Side REPL & Tool Inspector
**Goal:** Implement the user interfaces for configuring and extracting logs.
1. **REPL Interceptor (`src/liteagent/cli/main.py`)**:
   - Intercept and implement the following client-side commands without invoking the LLM:
     - `/addlog <file_path>`
     - `/addissue <issue_description>`
     - `/logs`
     - `/issues`
     - `/rmlog <id>` / `/rmissue <id>`
     - `/editlog <id> <new_path>` / `/editissue <id> <new_description>`
     - `/renameid <old_id> <new_id>`
   - Implement `/extractlogs [--empty]` to trigger the extraction engine manually. Ensure `--empty` bypasses the LLM description generation.
2. **Tool Inspector Integration**:
   - Register the extraction actions in the Tool Inspector web UI (`liteagent chat -i`).
   - Add the two parameter-less options: `extract-log-with-description` and `extract-log-empty`.
   - Ensure the UI reflects the real-time progress feedback identical to the CLI.

## Phase 4: Analysis Pipeline & Integration
**Goal:** Connect the config, the logbase, and the LangGraph loop for root cause analysis.
1. **The `/analyze` Command**:
   - Implement `/analyze <issue_id> <log_id1> [log_id2] ...` in the REPL.
   - Ensure it triggers the incremental Logbase Extraction Engine first.
   - Automate the parsing and indexing of the specified logs into SQLite FTS5 using the existing `LogDiscoverer` and `LogParser`.
2. **System Prompt Injection**:
   - Modify the LangGraph planner's context injection.
   - Dynamically inject the selected issue description, log paths, and the enriched `logbase.json` content into the agent's system prompt before the analysis loop starts.
3. **Tool Pruning**:
   - Delete `src/liteagent/tools/extract_log_patterns_tool.py` as it is now obsolete.

## Phase 5: Verification & Testing
**Goal:** Validate the end-to-end functionality.
1. **Efficiency Test**: Run `/extractlogs` on an unmodified codebase twice to ensure 0 LLM calls on the second run.
2. **Incremental Test**: Modify a single method, run `/extractlogs`, and verify only that method is processed by the LLM.
3. **Diagnosis Test**: Run a full `/analyze` command with a mock issue and log file to verify the agent accurately links log entries to the source code using the `logbase.json` descriptions.

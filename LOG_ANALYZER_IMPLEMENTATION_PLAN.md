# LogAnalyzer Implementation Plan

This document breaks down the `LOG_ANALYZER_PLAN.md` into actionable implementation steps.

## Phase 1: Configuration Management ✅
**Goal:** Establish persistent storage for logs and issue configurations.
1. **Create Config Manager**: ✅
   - Created `src/liteagent/core/analyzer_config.py`.
   - Schema stores log paths and issue descriptions with 4-character unique IDs in `.liteagent/analyzer_config.json`.
   - Helper methods for add, edit, remove, rename, and list operations.

## Phase 2: Logbase Extraction Engine ✅
**Goal:** Build the system that parses code for log statements, generates descriptions, and tracks changes.
1. **AST Parsing & Hashing**: ✅
   - Created `src/liteagent/insight/logs/logbase_extractor.py`.
   - Leverages the existing `KnowledgeGraph` for method and log template data (no duplicate AST parsing).
   - Method-level SHA-256 hashing for incremental change detection.
   - Extracts `log_lines` and `line_range` for each method.
2. **LLM Integration**: ✅ (infrastructure ready)
   - Accepts an `llm_describe(method_name, source, log_lines)` callable for description generation.
   - Real-time progress callback `on_progress(current, total, method_name)` for CLI/Inspector.
3. **Persistence & Schema**: ✅
   - Saves to `.liteagent/logbase.json` in the strict hierarchy: `Filepath` → `Class` → `Method` → `{ log_lines, description, line_range }`.
   - Hashes saved separately in `.liteagent/logbase_hashes.json`.
4. **Incremental Efficiency**: ✅
   - Compares current hash against cached hash; reuses cached description if unchanged.

## Phase 3: Client-Side REPL & Tool Inspector ✅
**Goal:** Implement the user interfaces for configuring and extracting logs.
1. **REPL Interceptor (`src/liteagent/cli/main.py`)**: ✅
   - All slash commands implemented via `_handle_slash_command()`:
     - `/addlog <file_path>`
     - `/addissue <issue_description>`
     - `/logs`
     - `/issues`
     - `/rmlog <id>` / `/rmissue <id>`
     - `/editlog <id> <new_path>` / `/editissue <id> <new_description>`
     - `/renameid <old_id> <new_id>`
     - `/extractlogs [--empty]`
   - Old `/config-add-log` handler replaced.
2. **Tool Inspector Integration (`src/liteagent/cli/server.py`)**: ✅
   - Two parameter-less API endpoints added:
     - `POST /api/actions/extract-log-with-description`
     - `POST /api/actions/extract-log-empty`
   - Inspector HTML updated with "System Actions" panel containing two styled buttons.
   - `runExtraction()` JS function handles progress display and results.

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

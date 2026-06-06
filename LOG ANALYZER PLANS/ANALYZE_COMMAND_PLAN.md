# Analyze Command Execution Plan

## Command Syntax
`/analyze <issue_id> <log_id1> [log_id2] ...`

This command is the core orchestrator. It bridges the gap between static codebase knowledge, dynamic runtime logs, and the intelligent agent. When executed, the command runs through a strict, sequential pipeline.

---

## Step 1: Configuration Resolution
- **Lookup:** Query the `AnalyzerConfig` using the provided IDs to retrieve the full `issue_description` and the absolute file paths of the raw logs.
- **Validation:** Ensure the IDs exist in `.liteagent/analyzer_config.json` and that the targeted log files actually exist on the user's disk.
- **Failure State:** If an ID is invalid or a log file is missing, print a user-friendly error to the console and abort.

---

## Step 2: Incremental Logbase Extraction
Before analyzing anything, we must ensure our map of the codebase is perfectly synchronized.
- **Execution:** Trigger `LogbaseExtractor.extract(empty=False)`.
- **Latency Guard:** The extractor counts how many methods have changed hashes or lack descriptions. If this count **exceeds 10**, it automatically falls back to `empty=True` (skipping LLM description generation) to prevent the user from waiting 5 minutes for the command to start.
- **Output:** An up-to-date `.liteagent/logbase.json`. If no logs exist in the codebase at all, the command prints `"logbase.json is empty"` and aborts.

---

## Step 3: Relevance Filtering
We cannot feed the entire `logbase.json` to the LLM. It is too massive.
- **Execution:** Call `filter_relevant_logs(issue_description, project_dir)`.
- **Mechanism:** Uses the local `all-MiniLM-L6-v2` embedding model and BM25 Okapi to rank all codebase log statements against the `issue_description`.
- **Output:** A flattened, sorted list of the most highly relevant methods, their descriptions, and their exact log patterns.

---

## Step 5: Sub-Agent Initialization
Instead of hijacking the user's main chat session, `/analyze` will spin up an isolated **Diagnostic Sub-Agent**.
- **Clean State:** The sub-agent starts with an empty message history, completely isolated from the user's main chat.
- **System Prompt Creation:** The sub-agent receives a specialized diagnostic system prompt:
  ```text
  You are an expert diagnostic system investigating the following issue:
  "{issue_description}"
  
  Based on a semantic scan of the codebase, here are the code methods and log statements MOST likely related to this issue, ranked by relevance:
  {filtered_logbase_json}
  
  You have access to the raw runtime logs via your `search_logs` tool. Use the exact log strings above as your search queries to find where the application failed in the runtime logs.
  ```

---

## Step 6: Sub-Agent Execution (Diagnostic Mode)
- **Launch:** The isolated LangGraph loop is triggered. The CLI will wait for this sub-agent to fully complete its research before returning control to the user.
- **Real-Time Visibility:** Even though the state is isolated, the sub-agent's execution will be completely visible in the chat interface. You will see its `<think>` blocks and its `search_logs`/`search_code` tool calls streaming live, so you can watch it investigate the root cause step-by-step.
- **Restricted Toolset:** The sub-agent runs with a highly specialized set of tools (e.g., only `search_logs`, `search_code`, `trace_calls`) to keep it laser-focused on research.
- **Workflow:** The sub-agent autonomously traces the issue through the logs and code, ultimately generating a comprehensive root-cause analysis report.

---

## Step 7: Post-Analysis Handoff
Once the sub-agent finishes its diagnostic run:
- **Result Extraction:** The final root-cause report is extracted from the sub-agent.
- **Context Preservation:** The user's main chat history is completely untouched. All their previous conversations are still there.
- **Injection:** The sub-agent's final report is seamlessly injected into the main chat state as a new AI message.
- **Next Steps:** The user is back in standard "Chat Mode". They can read the report and immediately ask follow-up questions or say *"Great, please write a patch for that bug"*. The main agent can then use its file editing tools to fix the bug, armed with the sub-agent's research!

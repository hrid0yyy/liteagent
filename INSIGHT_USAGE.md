# Insight Engine - Usage Guide

The Insight Engine has been successfully integrated into your `liteagent` CLI. Six essential tools have been activated to provide robust code search and log analytics capabilities without overwhelming local LLMs (like those run via Ollama).

## Starting the Agent

You can start the agent normally. The Insight tools are automatically loaded unless explicitly disabled.

```bash
# Start an interactive chat
liteagent chat

# Run a single task
liteagent do "Analyze the recent errors in the logs"

# Disable Insight tools if you want a lighter session
liteagent chat --no-insight
```

## Available Tools

The agent now has native access to the following 6 powerful tools:

### Code Knowledge Tools
1. **`search_code(query: str, top_k: int = 8)`**
   - **What it does:** Performs a hybrid vector and keyword search across your codebase.
   - **When the agent uses it:** Whenever you ask "where is the payment logic?" or "how does user authentication work?".

2. **`get_project_map(path: str = ".")`**
   - **What it does:** Returns a shallow, depth-1 map of the specified directory.
   - **When the agent uses it:** To understand the high-level structure of your application incrementally (Progressive Disclosure).

### Log Analytics Tools
3. **`search_logs(query: str, is_plain: bool = True)`**
   - **What it does:** Queries the log index for specific keywords, error codes, or regex patterns.
   - **When the agent uses it:** When searching for a specific user ID or an exact error code in the logs.

## Log Configuration

To configure which log files the agent analyzes, there are **two main mechanisms** for finding logs, which you can configure using a `.env` file or environment variables.

### How the Agent Finds Logs
1. **Explicit Paths (`INSIGHT_LOG_PATHS`):** Provide an exact JSON list of files you want the agent to analyze. *(Default is `["C:/temp/codeshare-logs/app.log"]`)*
2. **Auto-Discovery (`INSIGHT_LOG_DISCOVERY`):** When set to `True`, the agent automatically scans your project workspace and recursively finds files ending in `.log`.

### How to Configure Logs per Project
The cleanest way to configure the agent to analyze the logs for a specific project (e.g., `D:\project_a`) is to create a `.env` file directly in the root of that project folder.

**Example `D:\project_a\.env`:**
```env
# Explicitly target specific log files
INSIGHT_LOG_PATHS='["D:/project_a/logs/app.log", "D:/project_a/logs/error.log"]'

# OR automatically discover all .log files in the project
INSIGHT_LOG_DISCOVERY=True
```

Once this file is created, navigate to `D:\project_a` in your terminal and run `liteagent chat -i`. The agent will automatically detect your project-specific `.env` file and use the correct logs.

*Note: You can also place this `.env` file globally in your home directory at `~/.liteagent/.env` to apply the same configuration across all projects.*

## Example Workflow

Here is how you can interact with the agent using these tools:

> **You:** "The server crashed last night. Find any errors in the logs and tell me what happened."
> 
> **Agent:** 
> 1. Uses `search_logs(query="ERROR")` to find recent error logs.
> 2. Identifies "HTTP_500 Payment Timeout" as a critical issue.
> 3. Uses `search_code(query="Payment Timeout")` to locate the relevant code.
> 4. Reads the file context using `read_file`.
> 5. Explains the root cause to you.

## Development Note

The underlying infrastructure (`ChromaDB`, `Tree-sitter`, `SQLite`) is scaffolded in `src/liteagent/insight/`. As you expand your indexing capabilities in the future, these tools will naturally inherit the enhanced graph and vector retrieval capabilities. The tools `get_symbol`, `get_class_hierarchy`, and `trace_workflow` have been marked as `[FOR FUTURE]` in the documentation and are deliberately excluded from this minimal implementation.

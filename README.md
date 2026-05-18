# LiteAgent

A lightweight, extensible coding agent CLI built with Python and LangGraph.

## Features
- **Clean Architecture**: Decoupled providers, tools, and graph logic.
- **High Efficiency**: Surgical file operations and workspace exploration.
- **Provider Agnostic**: Supports Ollama and NVIDIA NIM.
- **LangGraph Workflow**: Plan-Execute-Review cycle for reliable results.
- **Model Context Protocol (MCP)**: Extensible capabilities via external MCP servers (see `MCP-USAGE.md`).
- **Knowledge Base Integration**: Context-aware project wiki integration to automatically inform the agent.
- **Universal Tool Summarizer**: Dual-model architecture that intelligently compresses large tool payloads to save context tokens.

## Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -e .
   ```
3. Set up your `.env` file (see `.env.example`).

## Usage
Run a task:
```bash
liteagent do "List the files in the current directory and create a summary.txt"
```

Specify provider and model:
```bash
liteagent do "Refactor src/main.py" --provider nvidia --model meta/llama3-70b-instruct
```

## Project Structure
- `src/liteagent/cli/`: Typer interface and formatting.
- `src/liteagent/core/`: Configuration and state management.
- `src/liteagent/graph/`: LangGraph nodes and builder.
- `src/liteagent/providers/`: LLM API wrappers.
- `src/liteagent/tools/`: High-efficiency workspace and file tools.

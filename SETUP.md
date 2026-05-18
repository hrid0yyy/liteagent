# LiteAgent Setup Guide

Welcome to **LiteAgent**, a lightweight, extensible coding agent CLI built with Python and LangGraph. This guide will help you get the project running on your machine.

## Prerequisites
- **Python 3.10 or higher**
- **Ollama** (for local LLM support) or an **NVIDIA NIM API Key** (for cloud LLM support)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd liteagent
   ```

2. **Install globally (Recommended):**
   Use `uv` or `pipx` to automatically create an isolated environment and add the CLI to your global PATH:
   - **Using uv:**
     ```bash
     uv tool install -e .
     ```
   - **Using pipx:**
     ```bash
     pipx install -e .
     ```
   *(If you prefer a manual virtual environment, you can still use `python -m venv .venv` and `pip install -e .`, but you will need to activate the environment each time).* 

## Configuration

1. **Set up your environment variables:**
   Copy the example file to `.env`:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and add your `NVIDIA_API_KEY` or update your `OLLAMA_BASE_URL`.

2. **MCP Setup (Optional):**
   To use MCP tools, configure `mcp_servers.json` in your project root (see `mcp_servers.json.example` and `MCP-USAGE.md`).

3. **Global Config:**
   The tool also looks for a `.env` file in `~/.liteagent/.env`. You can move your secrets there for truly global use:
   ```bash
   mkdir ~/.liteagent
   cp .env ~/.liteagent/.env
   ```

4. **Summarizer Configuration (Optional):**
   The agent automatically compresses large tool outputs using a secondary lightweight model. You can customize this in your `.env` file (the defaults use openrouter):
   ```env
   SUMMARIZER_ENABLED=true
   SUMMARIZER_PROVIDER=openrouter
   SUMMARIZER_MODEL=openai/gpt-oss-120b:free
   SUMMARIZER_THRESHOLD=4000
   ```

## Usage

### 1. Single Task Mode
Use the `do` command for one-off tasks:
```bash
liteagent do "Create a summary of all .md files in this project"
```

### 2. Interactive Chat Mode
Use the `chat` command for a multi-turn conversation:
```bash
liteagent chat --provider nvidia -m minimaxai/minimax-m2.7 --crg
liteagent chat --provider nvidia -m minimaxai/minimax-m2.7 
```

### Options:
- `-p, --provider`: Choose between `ollama` (default) or `nvidia`.
- `-m, --model`: Override the default model (e.g., `minimax/minimax-m2.7`).
- `--crg`: Enable Knowledge Base (Code Review Graph) wiki integration for context-aware coding.

## Architecture
- **ReAct Loop**: Uses a Reasoning + Acting loop in LangGraph.
- **Surgical Tools**: High-precision tools for reading and modifying files without consuming excess tokens.
- **Provider Abstraction**: Easily swap LLM backends in `src/liteagent/providers/`.
- **Universal Tool Summarizer**: A Dual-Model node that automatically intercepts and compresses massive tool payloads to prevent context window overflow.
- **Model Context Protocol (MCP)**: Native integration for dynamic external tools via standardized servers.
- **Knowledge Base**: Employs a WikiKnowledgeManager to dynamically inject repository-specific insights.

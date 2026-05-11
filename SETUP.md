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

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment:**
   - **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
   - **macOS/Linux:** `source .venv/bin/activate`

4. **Install the package in editable mode:**
   ```bash
   pip install -e .
   ```

## Configuration

1. **Set up your environment variables:**
   Copy the example file to `.env`:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and add your `NVIDIA_API_KEY` or update your `OLLAMA_BASE_URL`.

2. **Global Access (Optional but Recommended):**
   To run `liteagent` from any directory, add the virtual environment's `Scripts` (Windows) or `bin` (macOS/Linux) folder to your system's `PATH`.

   **Windows PowerShell:**
   ```powershell
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\path\to\liteagent\.venv\Scripts", "User")
   ```
   *(Note: Replace `C:\path\to\liteagent` with your actual project path. Restart your terminal after running this.)*

3. **Global Config:**
   The tool also looks for a `.env` file in `~/.liteagent/.env`. You can move your secrets there for truly global use:
   ```bash
   mkdir ~/.liteagent
   cp .env ~/.liteagent/.env
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
liteagent chat --provider nvidia
```

### Options:
- `-p, --provider`: Choose between `ollama` (default) or `nvidia`.
- `-m, --model`: Override the default model (e.g., `minimax/minimax-m2.7`).

## Architecture
- **ReAct Loop**: Uses a Reasoning + Acting loop in LangGraph.
- **Surgical Tools**: High-precision tools for reading and modifying files without consuming excess tokens.
- **Provider Abstraction**: Easily swap LLM backends in `src/liteagent/providers/`.

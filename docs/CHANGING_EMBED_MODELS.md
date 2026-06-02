# Guide: Changing Embedding Models

LiteAgent's Insight Engine supports multiple embedding models for its vector database (ChromaDB). You can easily switch between them depending on whether you need extreme speed (MiniLM) or high code accuracy/context size (Nomic).

## Supported Models

1. **`minilm` (Default):** `all-MiniLM-L6-v2`
   - **Size:** ~22MB
   - **Context Limit:** 256 tokens
   - **Best for:** Rapid prototyping, extreme low latency, running on old CPUs.

2. **`nomic`:** `nomic-ai/nomic-embed-text-v1.5`
   - **Size:** ~520MB
   - **Context Limit:** 8,192 tokens
   - **Best for:** Production C# applications. Its massive context window allows it to index entire classes without truncating them.

3. **`bge`:** `BAAI/bge-m3`
   - **Size:** ~2.2GB
   - **Context Limit:** 8,192 tokens
   - **Best for:** Enterprise retrieval requiring multi-language exact matching.

---

## How to Switch Models

LiteAgent determines which model to use by reading the `LITEAGENT_EMBED_MODEL` environment variable on startup.

### ⚠️ CRITICAL STEP: Wipe the Old Database
Every embedding model outputs vectors of a different mathematical size (e.g., MiniLM outputs 384 dimensions, Nomic outputs 768). If you try to run a new model on an old database, the system will crash.

**Whenever you change models, you MUST delete the existing ChromaDB folder in your project:**
Delete the following folder in your target project:
`[Your-Project-Dir]/.liteagent/insight/chromadb/`

*(When you start LiteAgent again, it will automatically parse your source files and rebuild the database using the new model).*

### Starting LiteAgent with a New Model

**On Windows (PowerShell):**
```powershell
# Set the environment variable for your current terminal session
$env:LITEAGENT_EMBED_MODEL="nomic"

# Start the agent
liteagent chat -p nvidia -m minimaxai/minimax-m2.7 -i
```

**On Mac/Linux (Bash):**
```bash
# Provide the environment variable inline
LITEAGENT_EMBED_MODEL="nomic" liteagent chat -p nvidia -m minimaxai/minimax-m2.7 -i
```

To switch back to the default, just set `$env:LITEAGENT_EMBED_MODEL="minilm"`, delete the `chromadb` folder again, and restart the agent!

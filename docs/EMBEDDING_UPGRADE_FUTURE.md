# Future Action Plan: Embedding Model Upgrade

## The Limitation
`all-MiniLM-L6-v2` is extremely fast and lightweight, but it is a general-purpose English NLP model with only 384 dimensions and a tiny 256-token context window. It struggles with dense code syntax, variable naming conventions, and large code blocks.

## The Objective
Upgrade LiteAgent to use modern, code-aware, high-context embedding models. This will drastically improve semantic search accuracy, reduce the need for aggressive chunking, and allow the agent to retrieve entire complex files based on abstract user prompts.

## Detailed Upgrade Path

### 1. Target Models for Consideration

#### A. Nomic Embed Code (7B)
- **Size:** ~14 GB (7 Billion Parameters)
- **Context Window:** 8,192 tokens.
- **Pros:** State-of-the-Art for code. Based on Qwen2 architecture, heavily optimized for code-to-code and natural language-to-code retrieval. It understands programming logic and class structures infinitely better than text-only models.
- **Cons:** Slow on local machines unless using a dedicated high-memory GPU (8GB+ VRAM).

#### B. Qwen3-Embedding-0.6B
- **Size:** ~1.2 GB (600 Million Parameters)
- **Context Window:** 8,192 tokens.
- **Pros:** The Efficiency Sweet Spot. Small enough to run incredibly fast on a standard laptop CPU but outperforms larger models on code retrieval benchmarks. It inherently understands programming languages because the underlying Qwen base model is highly proficient in coding.
- **Cons:** Less capable than the massive 7B or 8B versions for highly complex, multi-file semantic reasoning.

#### C. BGE-M3 (BAAI)
- **Size:** ~2.2 GB (560 Million Parameters)
- **Context Window:** 8,192 tokens.
- **Pros:** The Enterprise Standard. Supports "Hybrid Retrieval" natively and excels at finding exact variable names or method names across a multilingual codebase.
- **Cons:** Moderate CPU or low-end GPU required; slightly heavier than Qwen3-0.6B.

#### D. Nomic-Embed-Text-v1.5
- **Size:** ~520 MB (137 Million Parameters)
- **Context Window:** 8,192 tokens.
- **Pros:** Extremely fast and solves the immediate 256-token context limit of MiniLM. Fits in memory very easily.
- **Cons:** It is a general-purpose text model, not explicitly trained for complex programming syntax or brackets. It will provide a structural upgrade but might lag behind Qwen3-0.6B in pure code intelligence.

### 2. Implementation Steps (`providers.py`)

We will update `InsightProviders` to support dynamic embedding model selection via configuration or environment variables, matching how `ToolProviderFactory` handles the LLM providers.

#### Step A: Factory Pattern for Embeddings
Refactor `providers.py` to support dynamic embeddings:
```python
import os
from chromadb.utils import embedding_functions

embed_provider = os.environ.get("LITEAGENT_EMBEDDING_PROVIDER", "local")

if embed_provider == "ollama":
    emb_fn = embedding_functions.OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings", 
        model_name="nomic-embed-text"
    )
elif embed_provider == "openai":
    emb_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.environ.get("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
else:
    # Fallback to current mini model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
```

#### Step B: Dynamic Chunk Sizing
If the user is running `nomic-embed-text` with an 8k context window, aggressive chunking (from the immediate action plan) is no longer necessary.
The `ASTParser` should dynamically adjust its chunking strategy based on the active model:
- `all-MiniLM-L6-v2` -> 250 token chunks
- `nomic-embed-text` -> 6000 token chunks (or no chunking for most files)
- `text-embedding-3` -> 8000 token chunks

### 3. Vector Database Migration Strategy
Changing an embedding model completely changes the mathematical vector dimensions (e.g., from 384 dimensions to 1536).
- If a user switches embedding models, the old ChromaDB instance will crash because the dimensions don't match.
- **Logic Required:** The system must detect a model swap (e.g., storing the current model name in SQLite). If the model name changes on startup, the system must forcefully wipe the `chromadb` directory and trigger a full re-index.

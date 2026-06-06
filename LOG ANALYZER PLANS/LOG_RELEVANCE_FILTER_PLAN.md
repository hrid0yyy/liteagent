# Log Relevance Filter Plan

## Overview
During the `/analyze` command, injecting the entire `logbase.json` into the agent's context could easily exceed token limits (or distract the agent with unrelated logs). 

To solve this, we will build a **System Call** (an internal Python function, not an agent tool) that acts as a pre-filter. It will take the `issue_description`, evaluate `logbase.json`, and return only the subset of logs/methods that are conceptually related to the issue.

## 1. Function Signature & Location
**File:** `src/liteagent/insight/logs/relevance_filter.py`

```python
def filter_relevant_logs(issue_description: str, project_dir: Path, provider: Any) -> dict:
    """
    Evaluates logbase.json against the issue description.
    Returns a filtered subset of the logbase containing only relevant methods.
    """
```

## 2. Execution Flow

### A. Load and Flatten Data
- Load `.liteagent/logbase.json`.
- Flatten the nested dictionary (`Filepath -> Class -> Method`) into a flat list of items to make it easier to chunk and pass to the LLM. 
  - *Example item:* `{"id": "file.cs::MyClass::MyMethod", "description": "...", "log_lines": [...]}`

### B. Intelligent Chunking
- If the codebase has hundreds of logged methods, passing them all at once will fail context limits.
- Group the flattened methods into chunks (e.g., 20-30 methods per chunk depending on token limits).

### C. BM25 Lexical Scoring
- We will leverage the `rank_bm25` (BM25Okapi) library which is already installed for the `HybridRetriever`.
- We build an ephemeral, in-memory BM25 index out of the `logbase.json` entries (using the method's name and log lines).
- This handles exact keyword matches (e.g., matching the exact error code or exact variable names).

### D. Semantic Vector Embeddings (The "Spice")
- If the methods in `logbase.json` have LLM-generated `description` fields, we can perform true **Semantic Search**.
- We will use the locally downloaded **`all-MiniLM-L6-v2`** model (via `sentence-transformers`) to generate dense vector embeddings for each method's description.
- These local embeddings will be cached alongside the logbase to avoid re-embedding.
- When `/analyze` is called, we embed the `issue_description` instantly and completely offline.
- We calculate the **Cosine Similarity** between the issue embedding and the method description embeddings.
- **Why this is game-changing:** If the issue says *"teammate network discovery drops"*, semantic search will match a method described as *"handles mDNS connection timeouts"*, even though they share zero exact keywords! It runs entirely locally, meaning zero API costs or rate limit concerns.

### E. Hybrid Reconstruction (Ranked Output)
- We will combine the BM25 Lexical Score and the Semantic Vector Score into a single unified `relevance_score`.
- Since we are ranking by relevance, recreating the nested `Filepath -> Class -> Method` dictionary isn't ideal because dictionaries are harder for the LLM to read sequentially by importance.
- Instead, we will reconstruct the data into a **flat, ordered list** of methods. The LLM will read the most relevant methods first.
- The output format will look like:
  ```json
  [
    {
      "file": "DiscoveryService.cs",
      "class": "DiscoveryService",
      "method": "StartAdvertising",
      "score": 8.45,
      "description": "Starts mDNS...",
      "log_lines": ["..."]
    },
    ...
  ]
  ```

## 3. Usage in the `/analyze` Command
Inside `_handle_slash_command` (for `/analyze`):
1. Retrieve the `issue_description` using the `issue_id`.
2. Retrieve the log paths using the `log_id`.
3. Call `filtered_logbase = filter_relevant_logs(issue_description, project_dir, current_llm_provider)`.
4. Inject `filtered_logbase` into the LangGraph system prompt.
5. The agent now has a highly focused map of exactly which log lines to look for and where they come from in the code.

## 4. Edge Cases to Handle
- **Missing Descriptions:** If a method in `logbase.json` lacks an LLM description (e.g., if the user previously ran `/extractlogs --empty`), the Semantic Vector tier gracefully skips that method and relies exclusively on its BM25 Lexical Score.
- **Empty Codebase Logs:** If the codebase genuinely has zero log statements (the `logbase.json` is empty), the `/analyze` command will simply output `"logbase.json is empty"` to the console and halt the process, rather than trying to run the full agent loop.
- **Latency Protection (>10 Methods):** If the `/analyze` command detects that more than 10 methods need new descriptions, it will **skip description generation** (acting like `empty=True`) to prevent massive API costs and user wait times. For those methods, the Relevance Filter will automatically fall back to pure BM25 keyword matching until the user manually runs a full `/extractlogs`.

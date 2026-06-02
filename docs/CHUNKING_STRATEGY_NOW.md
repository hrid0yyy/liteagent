# Immediate Action Plan: Code Chunking Strategy

## The Problem
The current vector search implementation uses `all-MiniLM-L6-v2`, which possesses a strict 256-token limit. The `ASTParser` presently indexes entire C# classes and methods as single monolithic documents. When these documents exceed ~256 tokens (roughly 40 lines of code), ChromaDB silently truncates the content, blinding the semantic search to the bulk of the logic.

## The Solution
We must implement a **Chunking Strategy** within the `ASTParser` prior to vector upsertion. Instead of inserting large strings, we will split the code blocks into smaller, overlapping chunks that fit safely within the 256-token context window.

## Detailed Implementation Plan

### 1. Integrate a Text Splitter
Introduce `RecursiveCharacterTextSplitter` from `langchain_text_splitters` (or write a lightweight custom equivalent).
- **Target Chunk Size:** ~800 characters (this safely approximates 200-250 WordPiece tokens).
- **Chunk Overlap:** ~150 characters. Overlap ensures that context at the boundary between chunks is not lost.
- **Separators:** `["\n\n", "\n", " ", ""]` to ensure splits happen at logical boundaries (like empty lines between code statements) rather than cutting words or variables in half.

### 2. Update `ASTParser.py` Logic
When processing `method_declaration`, `class_declaration`, or raw files, we will modify the upsert logic:
- **Current Behavior:** 
  ```python
  self.code_collection.upsert(ids=[qname], documents=[source], metadatas=[{"name": name}])
  ```
- **New Behavior:**
  1. Detect if `len(source) > 800`.
  2. If yes, chunk the `source` into a list of strings: `chunks = split_text(source)`.
  3. Create unique IDs for each chunk (e.g., `f"{qname}_chunk_0"`, `f"{qname}_chunk_1"`).
  4. Upsert all chunks into ChromaDB, keeping the original metadata so the retrieval phase still maps it back to the exact file and symbol:
     ```python
     self.code_collection.upsert(
         ids=[f"{qname}_chunk_{i}" for i in range(len(chunks))], 
         documents=chunks, 
         metadatas=[{"name": name, "file_path": file_path}] * len(chunks)
     )
     ```

### 3. Maintain SQLite Integrity
The SQLite `KnowledgeGraph` (`knowledge.db`) does not suffer from token limits. Therefore:
- Do **not** chunk the code inserted into SQLite. 
- Keep `self.graph_store.insert_symbol(..., source)` exactly as it is.
- During retrieval, ChromaDB will match `method.ValidateToken_chunk_3`. The `HybridRetriever` will strip the `_chunk_X` suffix, query SQLite for the full `method.ValidateToken` symbol, and return the *entire* method to the LLM. This provides the best of both worlds: highly accurate semantic matching on small code chunks, but full-context code delivery to the LLM.

### 4. Special Handling for Documentation
For `.md` or `.txt` files parsed by the fallback mechanism, apply the exact same text splitter before insertion.

### 5. Re-indexing
Once implemented, users must delete the `.liteagent/insight/chromadb` folder to force a clean re-indexing of their projects with the new overlapping chunks.

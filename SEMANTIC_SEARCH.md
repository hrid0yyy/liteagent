# Semantic Search Architecture

The Insight Agent in `liteagent` has been upgraded to support **True Semantic Search** using Vector Embeddings. This allows the agent to find code and logs based on their *meaning* rather than exact keyword matches (e.g., searching for "login" will correctly identify `AuthService`).

## Technology Stack
1. **Embedding Model:** `all-MiniLM-L6-v2` (via the `sentence-transformers` library)
2. **Vector Database:** `ChromaDB` (Local vector storage)
3. **Knowledge Graph:** `SQLite` (Relational storage for AST dependencies and exact metadata)

## How It Works (The Hybrid Approach)
We use a **Hybrid Architecture** because Vector Databases are excellent for finding meaning but terrible at mapping strict relationships (like call graphs) or precise locations (like line numbers). 

1. **Indexing Phase (`ASTParser`)**
   - The parser reads the C# source code and extracts classes and methods.
   - It saves the exact metadata (line numbers, file paths) and relationships to **SQLite**.
   - Simultaneously, it generates a vector embedding for the source code and stores it in **ChromaDB**, using the exact same unique ID (`qualified_name`) as SQLite.

2. **Retrieval Phase (`HybridRetriever`)**
   - When a search is triggered (e.g., `"How are tokens validated?"`), the query is converted into a vector embedding.
   - **ChromaDB** mathematically finds the top matching source code vectors and returns their IDs (e.g., `method.ValidateToken`).
   - The agent then queries **SQLite** using those exact IDs to pull the rich metadata (file path, exact source code, line numbers).
   - *Fallback Mechanism:* If the vector search fails or the model hasn't downloaded yet, it gracefully falls back to the previous SQLite keyword/substring matching mechanism.

## Performance Profile
- **Local & Private:** Everything runs 100% locally. Code is never sent to an external API like OpenAI.
- **Lightweight:** `all-MiniLM-L6-v2` is only ~90MB and consumes less than 300MB of RAM.
- **CPU Friendly:** Because the model is so small, embeddings are calculated incredibly fast directly on the CPU, making it perfectly suited for developers running this locally alongside other heavy tools.

## Real-time Auto-Sync (Watchdog)
To ensure the agent is never working with stale code, the architecture integrates the `watchdog` library:
1. When the agent starts, it spawns a lightweight background thread watching your project directory.
2. The moment you save a `.cs` file in your editor, `watchdog` triggers the `on_modified` event.
3. The `ASTParser` intercepts this event, clears out any old SQLite/ChromaDB references for that specific file, and instantly re-embeds the new code.
4. **Result:** The agent's knowledge base is updated in real-time, matching your exact code state without ever requiring a CLI restart!

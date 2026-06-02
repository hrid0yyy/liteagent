# Embedding Model Benchmark Plan: MiniLM vs. Nomic

This plan outlines exactly how we will inflate the `CodeShareTest` project and benchmark the real-world performance, latency, and context-window limitations of both `all-MiniLM-L6-v2` and `nomic-embed-text-v1.5`.

## Phase 1: Artificially Inflating the Codebase
To truly test these models, we need a codebase large enough to trigger the 256-token limit of MiniLM and challenge the processing speed of both models.

**Action:** We will write a small Python script to inject massive files into `tests/test-project/CodeShareTest`:
1. **The God Class (`GodService.cs`):** A massive 2,000-line C# class. Crucially, we will place a highly specific method (e.g., `public void ExecuteCryptographicKeyRotation()`) at the very bottom (line 1,950).
2. **The Noise Files (`LegacyData_01.cs` to `LegacyData_50.cs`):** 50 C# files containing thousands of lines of dummy business logic, switch statements, and repetitive code to simulate a bloated enterprise application.
3. **The Semantic Target (`AdvancedRateLimiter.cs`):** A file that implements "sliding window token bucket logic". We will NOT use the word "rate limit" inside the code; we will test if the model can semantically understand what the code does.
4. **The Clone Army (`PaymentGateway_*.cs`):** We will create 10 distinct but highly similar `PaymentProcessor` classes. All will have functions named `ProcessTransaction()`. However, **only one** (the Ground Truth) will specifically handle "Stripe asynchronous webhooks with Ed25519 signature verification". The rest will handle generic credit cards, PayPal, bank transfers, etc.

## Phase 2: The Benchmark Tests

We will run three distinct tests using the `search_code` tool.

### Test A: Cold-Start Indexing Latency
**Goal:** Measure how long it takes for the `ASTParser` to generate embeddings for a massive codebase from scratch.
- **Metric:** Time taken from starting the agent until the `chromadb` directory finishes building.
- **Hypothesis:** `minilm` will be drastically faster at indexing because it generates smaller vectors (384 dimensions) and silently skips reading the bottom halves of large files. `nomic` will take longer because it actually processes the entire 8k context window.

### Test B: The Truncation Test (The God Class)
**Goal:** Prove the 256-token limitation of MiniLM.
- **Query:** `search_code("cryptographic key rotation")`
- **Hypothesis:** 
  - `minilm` will **FAIL**. Because the method is on line 1,950, it gets truncated and the embedding vector knows nothing about it.
  - `nomic` will **PASS**. Its 8,192 token limit will comfortably swallow the 2,000-line class and retrieve it.

### Test C: Abstract Semantic Reasoning
**Goal:** Test raw intelligence and code comprehension.
- **Query:** `search_code("How is the sliding window token bucket implemented?")`
- **Hypothesis:** `minilm` may fail to capture complex logical abstraction due to its small size, relying on exact keyword matches. `nomic` should excel at recognizing the programmatic patterns of a rate limiter even without explicit variable names.

### Test D: High-Fidelity Semantic Disambiguation
**Goal:** Test which model can distinguish between highly similar code structures to find the exact needle in the haystack.
- **Query:** `search_code("Stripe webhook processing with Ed25519 signatures")`
- **Hypothesis:** `minilm` might get confused by the high overlap of generic payment terminology and return the wrong `PaymentProcessor`. `nomic` should perfectly identify the specific Ground Truth class.

## Phase 3: Execution Protocol

You will execute the tests by following these exact steps:

**Round 1: MiniLM Benchmark**
1. Delete `tests/test-project/CodeShareTest/.liteagent`
2. Open terminal: `$env:LITEAGENT_EMBED_MODEL="minilm"`
3. Start the agent: `liteagent chat -p nvidia -m minimaxai/minimax-m2.7 -i`
4. Time the initial boot/indexing phase.
5. Ask the agent: *"Search the code for cryptographic key rotation"*
6. Ask the agent: *"Search the code for sliding window token bucket implementation"*
7. Ask the agent: *"Find the Stripe webhook processor that uses Ed25519 signatures"*
8. Record results.

**Round 2: Nomic Benchmark**
1. Delete `tests/test-project/CodeShareTest/.liteagent`
2. Open terminal: `$env:LITEAGENT_EMBED_MODEL="nomic"`
3. Start the agent (Wait for the ~520MB download to complete if it's the first time).
4. Time the initial boot/indexing phase.
5. Ask the agent the exact same three queries.
6. Record results and compare!

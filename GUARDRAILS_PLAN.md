# Plan

## Problem
Add guardrails to the agent runtime:
- Block duplicate tool calls within the same user turn via a fingerprint hash.
- Generate an initial step list for each user query and hard-stop after the last step (no replans).
- Stop after 2 consecutive tool failures and report the blocking issue.

## Approach
- Extend agent state to track plan steps, current step index, tool-failure streak, and a per-turn tool fingerprint list (JSON-serializable).
- Introduce a plan-then-execute flow: planning node (no tools) → step executor (with tools) → finalizer (no tools).
- Enforce guardrails in executor (duplicate detection + failure tracking) and in the finalizer (hard-stop conditions).
- Reset per-turn guardrail state on each new user input in the CLI.

## Todos
1. Update `core/state.py` and CLI state initialization to include plan steps, step index, tool-failure streak, and per-turn fingerprints.
2. Add a planning node that generates a numbered step list (no tools) and stores it in state.
3. Update the step executor to focus on the current step only, emit at most one tool call, and advance the step index after each tool execution cycle.
4. Add a finalizer node that forces a final response when step limits or failure thresholds are reached.
5. Implement duplicate tool detection in `executor.py` using hash(tool name + normalized args); emit a tool error payload and count it as a failure.
6. Rewire `graph/builder.py` to the new flow with guardrail-aware conditional edges; update logging for guardrail triggers.

## Notes
- Use stable JSON serialization (sorted keys) when fingerprinting arguments to avoid ordering issues.
- Keep new state fields JSON-serializable so session persistence continues to work.
- When hard-stopping (step limit or 2x tool failures), the finalizer should summarize what was done and why it stopped.

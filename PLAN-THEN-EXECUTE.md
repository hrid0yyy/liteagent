Now I have a thorough understanding of the entire codebase. Here's a comprehensive plan for implementing a **Plan-then-Execute** architecture:

---

## Architecture Design: Plan-then-Execute

### Graph Flow
```
START → planner → step_executor → replanner → (is_complete?) → END
                                               ↓ (not complete)
                                          step_executor → replanner → ...
```

### Three Core Nodes

**1. `planner_node`** (no tools — pure reasoning)
- Takes the user request
- Calls LLM **without tools** to generate a structured step-by-step plan
- Output: `plan` = list of step descriptions, `current_step_index` = 0

**2. `step_executor_node`** (with tools — executes one step)
- Reads `plan[current_step_index]` as the current task
- Calls LLM **with tools** to execute that specific step
- Runs the tool calls and collects results
- Output: tool results in `messages`, completed step info in `past_steps`

**3. `replanner_node`** (no tools — reviews & decides)
- Reviews what was accomplished vs. the remaining plan
- Three possible outcomes:
  - **Continue** → increment `current_step_index`, proceed to next step
  - **Replan** → generate a new plan based on what happened
  - **Complete** → set `is_complete = True`, provide final summary

### State Changes (`core/state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[List[dict], add]           # conversation history
    plan: List[str]                                 # ordered step descriptions (overwritten by planner/replanner)
    current_step_index: int                         # which step we're executing (overwritten by replanner)
    past_steps: Annotated[List[dict], add]          # [{"step": "...", "result": "..."}, ...]
    tool_outputs: Annotated[List[dict], add]        # tool execution results
    errors: Annotated[List[str], add]               # errors
    is_complete: bool                               # task completion flag
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `core/state.py` | **Modify** | Add `plan`, `current_step_index`, `past_steps` fields; remove unused `plan: str` |
| `graph/nodes/planner.py` | **Rewrite** | New planning node that generates structured plan without tools |
| `graph/nodes/executor.py` | **Rewrite** | Simplified to execute the current step from the plan |
| `graph/nodes/replanner.py` | **Create** | New node that reviews progress and decides continue/replan/complete |
| `graph/builder.py` | **Rewrite** | New graph structure with 3 nodes and conditional edges |
| `cli/main.py` | **Modify** | Update state initialization to include new fields; update event handling for new node names |

### Key Design Principles

1. **Separation of concerns**: Planning (what to do) is separate from execution (how to do it)
2. **Replanning capability**: If a step fails or reveals new information, the replanner can adjust the plan dynamically
3. **Structured progress tracking**: `past_steps` records what's been done, `current_step_index` tracks where we are
4. **Clean state management**: `plan` and `current_step_index` are overwritten (not appended), while `messages`, `past_steps`, `tool_outputs`, and `errors` use the `add` reducer

### Why This Is Better Than the Current ReAct

| Aspect | Current (ReAct) | Proposed (Plan-Execute) |
|--------|-----------------|------------------------|
| Planning | None (reactive) | Explicit upfront plan |
| Transparency | Hard to know overall progress | Clear plan with step tracking |
| Error recovery | LLM decides on the fly | Replanner can restructure the plan |
| Efficiency | May wander without clear direction | Focused execution per step |
| Cost | More LLM calls (each decides next step) | Fewer decisions (plan once, execute, replan only if needed) |

---

Shall I proceed with the implementation? If so, please **toggle to Act mode**.
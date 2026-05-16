## Found the Bug! Tool Call Format is Broken

Looking at the session log, I can see the problem:

### The Issue

The agent is outputting tool calls as **plain text** instead of proper tool call format:

```
"content": "<tool_name>get_workspace_info</tool_name>\n<tool_name>get_workspace_info</tool_name>..."
```

This is wrong! It should be a proper tool call that the executor can process.

### Root Cause

The **knowledge base context is confusing the model**. The model (qwen3.5:2b) is:
1. Including "thinking" blocks in the response
2. Outputting tool names as text instead of making actual tool calls
3. Getting confused by the large KB context

### Solutions

**Option 1: Reduce KB Context Size**
Add to your `.env`:
```
CRG_CONTEXT_MAX_CHARS=5000
```

**Option 2: Use a Better Model**
The `qwen3.5:2b` model might not handle tool calling well with large contexts. Try:
```bash
liteagent chat --provider ollama -m llama3.2 --crg
```

**Option 3: Fix the System Prompt**
The KB context might be interfering with the tool calling instructions. I need to fix the planner to ensure the KB context doesn't break tool calling.

### Immediate Fix

Please **toggle to Act mode** and I'll:
1. Reduce the default KB context size
2. Fix the system prompt to ensure tool calling works with KB enabled
3. Add a safeguard to truncate KB if it's too large
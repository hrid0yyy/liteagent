from typing import Dict, Any
from ...core.state import AgentState
from ...core.logger import log_event, log_error
from ...providers.base import BaseProvider
from ...tools.registry import registry
import os

async def planner_node(state: AgentState, provider: BaseProvider) -> Dict[str, Any]:
    """Core Agent Node (ReAct): Reasons about the task and decides on actions."""
    messages = state["messages"]
    cwd = os.getcwd()
    
    system_prompt = {
        "role": "system",
        "content": (
            f"You are a coding agent. Current directory: {cwd}\n\n"
            "CRITICAL RULES (DO NOT IGNORE):\n"
            "1. SINGLE TOOL CALL: You MUST ONLY CALL ONE TOOL AT A TIME. Do not attempt to call multiple tools in the same response.\n"
            "2. ZERO HALLUCINATION: You MUST NOT guess or make up file names, directory contents, or code. "
            "If the user asks to see files or asks about the project, you MUST call 'get_workspace_info' FIRST.\n"
            "3. READ FRESHNESS FIRST: Before re-reading a file, call 'check_file_freshness' and only call 'read_file' when 'should_read' is true or user explicitly asks to reread.\n"
            "4. READ BEFORE MODIFY: Always 'read_file' before 'modify_file' to ensure you have the exact content.\n"
            "5. REASONING: Briefly explain your thought process before calling a tool.\n"
            "6. CONVERSATION: For simple greetings (hi, hello) or questions about who you are, respond with text ONLY. No tools.\n"
            "7. COMPLETION: Once you have successfully executed the tools to fulfill the user's request, provide a final text summary and stop calling tools."
        )
    }
    
    # We only send the recent conversation history to keep the context clean
    full_messages = [system_prompt] + messages
    provider_tools = [provider.get_tool_schema(s) for s in registry.schemas]
    log_event(
        "planner_generate_start",
        "planner",
        {
            "cwd": cwd,
            "message_count": len(full_messages),
            "messages": full_messages,
            "tool_schema_count": len(provider_tools),
            "tool_schemas": provider_tools,
            "provider_model": getattr(provider, "model", ""),
        },
    )

    try:
        response = await provider.generate(full_messages, tools=provider_tools)
    except Exception as e:
        log_error("planner", e, {"stage": "provider_generate"})
        raise

    log_event(
        "planner_generate_end",
        "planner",
        {"response": response},
    )
    
    return {
        "messages": [response]
    }

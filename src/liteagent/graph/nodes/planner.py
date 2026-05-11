from typing import Dict, Any
from ...core.state import AgentState
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
            "3. READ BEFORE MODIFY: Always 'read_file' before 'modify_file' to ensure you have the exact content.\n"
            "4. REASONING: Briefly explain your thought process before calling a tool.\n"
            "5. CONVERSATION: For simple greetings (hi, hello) or questions about who you are, respond with text ONLY. No tools.\n"
            "6. COMPLETION: Once you have successfully executed the tools to fulfill the user's request, provide a final text summary and stop calling tools."
        )
    }
    
    # We only send the recent conversation history to keep the context clean
    full_messages = [system_prompt] + messages
    provider_tools = [provider.get_tool_schema(s) for s in registry.schemas]
    
    response = await provider.generate(full_messages, tools=provider_tools)
    
    return {
        "messages": [response]
    }

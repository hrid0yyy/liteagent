import asyncio
import json
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ..core.logger import log_event, log_error

class MCPManager:
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.tools_metadata: Dict[str, Dict[str, Any]] = {} # tool_name -> {server_name, original_schema}

    async def connect_to_server(self, name: str, config: Dict[str, Any]):
        """Connects to an MCP server and discovers its tools."""
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env")

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )

        try:
            log_event("mcp_connecting", "mcp_manager", {"server": name, "command": command, "args": args})
            
            # Use the exit stack to manage the lifecycle of the stdio client and session
            read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            
            await session.initialize()
            self.sessions[name] = session
            
            # Discover tools
            response = await session.list_tools()
            tools = response.tools
            
            for tool in tools:
                # We prefix tool names to avoid collisions if multiple servers provide same tool name
                # or just use the tool name if it's unique enough? 
                # The plan says "call_mcp_tool(server_name, tool_name, arguments)".
                # I'll store them as server_name__tool_name for internal registry
                internal_name = f"{name}__{tool.name}"
                self.tools_metadata[internal_name] = {
                    "server_name": name,
                    "tool_name": tool.name,
                    "schema": {
                        "name": internal_name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
            
            log_event("mcp_connected", "mcp_manager", {"server": name, "tools_count": len(tools)})
            return True
        except Exception as e:
            log_error("mcp_manager", e, {"server": name})
            return False

    async def call_tool(self, internal_name: str, arguments: Dict[str, Any]) -> str:
        """Calls a tool on a specific MCP server."""
        if internal_name not in self.tools_metadata:
            raise ValueError(f"Unknown MCP tool: {internal_name}")
            
        metadata = self.tools_metadata[internal_name]
        server_name = metadata["server_name"]
        tool_name = metadata["tool_name"]
        
        session = self.sessions.get(server_name)
        if not session:
            raise RuntimeError(f"Session for server '{server_name}' not found.")
            
        try:
            log_event("mcp_tool_call", "mcp_manager", {"server": server_name, "tool": tool_name, "args": arguments})
            result = await session.call_tool(tool_name, arguments)
            
            # Result is usually a List[TextContent | ImageContent | EmbeddedResource]
            # We convert it to a string for the agent.
            output = []
            for content in result.content:
                if hasattr(content, 'text'):
                    output.append(content.text)
                else:
                    output.append(str(content))
            
            return "\n".join(output)
        except Exception as e:
            log_error("mcp_manager", e, {"server": server_name, "tool": tool_name})
            raise e

    async def shutdown(self):
        """Closes all sessions and stops all servers."""
        await self.exit_stack.aclose()
        self.sessions.clear()
        self.tools_metadata.clear()

mcp_manager = MCPManager()

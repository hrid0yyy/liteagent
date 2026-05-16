# How to use Model Context Protocol (MCP) with LiteAgent

LiteAgent supports the Model Context Protocol (MCP), allowing you to extend the agent's capabilities by connecting to external MCP servers. This enables the agent to use tools like SQLite, web fetching, and more, provided by these servers.

## 1. Configuration

To use MCP, you need to create a `mcp_servers.json` file in the root directory of your project (the same directory where you run `liteagent`).

### Example `mcp_servers.json`

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "my_database.db"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

- **`command`**: The command to start the MCP server (e.g., `uvx`, `npx`, `python`).
- **`args`**: Arguments passed to the command.
- **`env`**: (Optional) Environment variables for the server process.

## 2. Starting LiteAgent

When you start LiteAgent using `liteagent do` or `liteagent chat`, it will automatically look for `mcp_servers.json`. 

You will see output indicating the connection status:

```text
Initializing 2 MCP servers...
  - Connected to sqlite
    - Registered tool: sqlite__read_query
    - Registered tool: sqlite__write_query
    - ...
  - Connected to fetch
    - Registered tool: fetch__fetch_url
```

## 3. Using MCP Tools

MCP tools are automatically prefixed with the server name (e.g., `sqlite__read_query`). The agent is aware of these tools and their schemas and will use them as needed during its execution.

You can ask the agent to perform tasks that require these tools, for example:
- "Read the schema of the local database using sqlite."
- "Fetch the content of https://example.com and summarize it."

## 4. Requirements

- **MCP Library**: The `mcp` Python package must be installed in your environment (already included in LiteAgent dependencies).
- **Server Runtimes**: Ensure you have the necessary runtimes for the MCP servers you want to use (e.g., `uv` for `uvx`, `Node.js` for `npx`).

## 5. Troubleshooting

- **Connection Failures**: Check if the `command` is available in your PATH. 
- **Tool Naming**: If multiple servers provide a tool with the same name, LiteAgent distinguishes them using the `server_name__tool_name` prefix.
- **Logs**: LiteAgent logs MCP events and errors to its session logs (located in `~/.liteagent` by default).

---
For more information on the Model Context Protocol, visit [modelcontextprotocol.io](https://modelcontextprotocol.io/).

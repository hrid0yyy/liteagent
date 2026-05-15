# Code Review Graph Tools Plan

## Overview

This document outlines the detailed plan for implementing CLI wrapper tools that allow the LiteAgent to directly use `code-review-graph` commands. These tools enable the agent to query code relationships, analyze impact, search code, and perform various code analysis tasks dynamically during a session.

---

## Goals

1. **Direct CLI Access**: Provide tools that wrap `code-review-graph` CLI commands
2. **Structured Output**: Return parsed JSON for easy agent consumption
3. **Error Handling**: Graceful handling of CLI failures
4. **Comprehensive Coverage**: Cover all major CLI command categories

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          LiteAgent Tool System                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Tool Registry                                │ │
│  │                                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │ │
│  │  │ File Ops     │  │ Workspace    │  │ Code Review Graph Tools  │  │ │
│  │  │              │  │              │  │                          │  │ │
│  │  │ - read_file  │  │ - get_info   │  │ - crg_query              │  │ │
│  │  │ - write_file │  │ - search     │  │ - crg_search             │  │ │
│  │  │ - modify_file│  │ - list_files │  │ - crg_traverse           │  │ │
│  │  └──────────────┘  └──────────────┘  │ - crg_impact             │  │ │
│  │                                        │ - crg_flows              │  │ │
│  │                                        │ - crg_flow               │  │ │
│  │                                        │ - crg_communities        │  │ │
│  │                                        │ - crg_community          │  │ │
│  │                                        │ - crg_architecture       │  │ │
│  │                                        │ - crg_hubs               │  │ │
│  │                                        │ - crg_bridges            │  │ │
│  │                                        │ - crg_gaps               │  │ │
│  │                                        │ - crg_surprises          │  │ │
│  │                                        │ - crg_questions          │  │ │
│  │                                        │ - crg_refactor           │  │ │
│  │                                        │ - crg_large_functions    │  │ │
│  │                                        │ - crg_status             │  │ │
│  │                                        │ - crg_build              │  │ │
│  │                                        │ - crg_update             │  │ │
│  │                                        └──────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│                                 │                                        │
│                                 ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     CLI Executor                                    │ │
│  │                                                                     │ │
│  │  - Subprocess management                                            │ │
│  │  - JSON parsing                                                     │ │
│  │  - Error handling                                                   │ │
│  │  - Timeout management                                               │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
src/liteagent/
├── tools/
│   ├── __init__.py
│   ├── registry.py           # Register CRG tools (MODIFY)
│   ├── code_review/
│   │   ├── __init__.py
│   │   ├── executor.py       # CLI command executor
│   │   ├── query.py          # Query tools
│   │   ├── search.py         # Search tools
│   │   ├── traverse.py       # Traverse tools
│   │   ├── impact.py         # Impact analysis tools
│   │   ├── flows.py          # Flow tools
│   │   ├── communities.py    # Community tools
│   │   ├── analysis.py       # Analysis tools (hubs, bridges, gaps)
│   │   ├── refactor.py       # Refactoring tools
│   │   └── management.py     # Build/update/status tools
│   └── ...
└── ...
```

---

## Tool Categories

### Category 1: Query Tools

Tools for querying code relationships.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_query` | `query <type> <target>` | Query relationships (callers, callees, imports, tests) |

### Category 2: Search Tools

Tools for semantic code search.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_search` | `search "<query>"` | Search for functions, classes, files |

### Category 3: Traverse Tools

Tools for graph traversal.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_traverse` | `traverse <node>` | Walk the graph from a node |

### Category 4: Impact Analysis Tools

Tools for analyzing change impact.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_impact` | `impact` | Blast radius analysis |
| `crg_affected_flows` | `affected-flows` | Affected execution flows |

### Category 5: Flow Tools

Tools for execution flow analysis.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_flows` | `flows` | List execution flows |
| `crg_flow` | `flow <id/name>` | Get flow details |

### Category 6: Community Tools

Tools for code community analysis.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_communities` | `communities` | List code communities |
| `crg_community` | `community <name>` | Get community details |
| `crg_architecture` | `architecture` | Architecture overview |

### Category 7: Analysis Tools

Tools for structural analysis.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_hubs` | `hubs` | Architectural hotspots |
| `crg_bridges` | `bridges` | Architectural chokepoints |
| `crg_gaps` | `gaps` | Structural weaknesses |
| `crg_surprises` | `surprises` | Unexpected coupling |
| `crg_questions` | `questions` | Review questions |

### Category 8: Refactoring Tools

Tools for refactoring assistance.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_refactor` | `refactor <action>` | Refactoring tools |
| `crg_large_functions` | `large-functions` | Find large code |

### Category 9: Management Tools

Tools for graph management.

| Tool | CLI Command | Description |
|------|-------------|-------------|
| `crg_status` | `status` | Graph status |
| `crg_build` | `build` | Build graph |
| `crg_update` | `update` | Update graph |

---

## Implementation Details

### Phase 1: CLI Executor

**File**: `src/liteagent/tools/code_review/executor.py`

```python
"""
CLI command executor for code-review-graph.
"""
import asyncio
import json
import shutil
from typing import Optional, Dict, Any, List
from ...core.logger import log_event, log_error


class CRGExecutor:
    """
    Executes code-review-graph CLI commands and returns parsed results.
    
    All commands use --format json for machine-readable output.
    """
    
    COMMAND = "code-review-graph"
    DEFAULT_TIMEOUT = 60  # seconds
    
    @classmethod
    async def execute(
        cls,
        args: str,
        timeout: int = None,
        cwd: str = ".",
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Execute a code-review-graph command.
        
        Args:
            args: Command arguments (e.g., "query callers_of my_func")
            timeout: Execution timeout in seconds
            cwd: Working directory
            format: Output format (json, table, markdown)
            
        Returns:
            Parsed JSON result or error dict
        """
        timeout = timeout or cls.DEFAULT_TIMEOUT
        
        # Check if command exists
        if not shutil.which(cls.COMMAND):
            return {
                "success": False,
                "error": f"{cls.COMMAND} command not found. Please install code-review-graph.",
                "data": None
            }
        
        # Build full command
        full_cmd = f"{cls.COMMAND} {args} --format {format}"
        
        log_event("crg_execute_start", "executor", {
            "command": full_cmd,
            "timeout": timeout,
            "cwd": cwd
        })
        
        try:
            process = await asyncio.create_subprocess_shell(
                full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip() or "Unknown error"
                log_event("crg_execute_error", "executor", {
                    "command": full_cmd,
                    "error": error_msg,
                    "returncode": process.returncode
                })
                return {
                    "success": False,
                    "error": error_msg,
                    "data": None
                }
            
            # Parse output
            output = stdout.decode().strip()
            
            if format == "json":
                try:
                    data = json.loads(output)
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed to parse JSON: {e}",
                        "data": output
                    }
            else:
                data = output
            
            log_event("crg_execute_success", "executor", {
                "command": full_cmd,
                "data_size": len(output)
            })
            
            return {
                "success": True,
                "error": None,
                "data": data
            }
            
        except asyncio.TimeoutError:
            log_event("crg_execute_timeout", "executor", {
                "command": full_cmd,
                "timeout": timeout
            })
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "data": None
            }
            
        except Exception as e:
            log_error("executor", e, {"command": full_cmd})
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    @classmethod
    async def check_available(cls) -> bool:
        """Check if code-review-graph is available."""
        return shutil.which(cls.COMMAND) is not None
```

### Phase 2: Query Tools

**File**: `src/liteagent/tools/code_review/query.py`

```python
"""
Query tools for code-review-graph.
"""
from typing import Optional, List
from .executor import CRGExecutor


async def crg_query(
    query_type: str,
    target: str,
    format: str = "json"
) -> str:
    """
    Query code relationships from the knowledge graph.
    
    Use this tool to find relationships between code elements like:
    - Who calls a function
    - What a function calls
    - Import relationships
    - Test relationships
    
    Args:
        query_type: Type of query. One of:
            - "callers_of": Find who calls a function
            - "callees_of": Find what a function calls
            - "imports_of": Find what a file imports
            - "importers_of": Find who imports a file
            - "tests_for": Find tests for a function/class
            - "file_summary": Get summary of a file
        target: The function name or file path to query
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with query results or error message.
        
    Examples:
        # Find all callers of process_payment function
        crg_query("callers_of", "process_payment")
        
        # Find what the auth module imports
        crg_query("imports_of", "src/auth.py")
        
        # Find tests for UserService class
        crg_query("tests_for", "UserService")
    """
    valid_types = [
        "callers_of", "callees_of", "imports_of", 
        "importers_of", "tests_for", "file_summary"
    ]
    
    if query_type not in valid_types:
        return f"Error: Invalid query_type. Must be one of: {', '.join(valid_types)}"
    
    result = await CRGExecutor.execute(
        f"query {query_type} {target}",
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 3: Search Tools

**File**: `src/liteagent/tools/code_review/search.py`

```python
"""
Search tools for code-review-graph.
"""
from typing import Optional
from .executor import CRGExecutor


async def crg_search(
    query: str,
    kind: Optional[str] = None,
    limit: int = 20,
    format: str = "json"
) -> str:
    """
    Search for functions, classes, or files by name or keyword.
    
    Use this tool to find code elements by name, keyword, or semantic meaning.
    
    Args:
        query: Search query string (e.g., "authentication", "payment", "User")
        kind: Filter by kind. One of: File, Class, Function, Type, Test. Optional.
        limit: Maximum number of results. Default: 20
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with search results or error message.
        
    Examples:
        # Search for authentication-related code
        crg_search("authentication")
        
        # Search for functions containing "process"
        crg_search("process", kind="Function")
        
        # Search for test files
        crg_search("test", kind="Test", limit=10)
    """
    cmd_args = f'search "{query}" --limit {limit}'
    
    if kind:
        valid_kinds = ["File", "Class", "Function", "Type", "Test"]
        if kind not in valid_kinds:
            return f"Error: Invalid kind. Must be one of: {', '.join(valid_kinds)}"
        cmd_args += f" --kind {kind}"
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 4: Traverse Tools

**File**: `src/liteagent/tools/code_review/traverse.py`

```python
"""
Traverse tools for code-review-graph.
"""
from typing import Optional
from .executor import CRGExecutor


async def crg_traverse(
    node_name: str,
    direction: str = "callees",
    max_depth: int = 3,
    max_nodes: int = 50,
    format: str = "json"
) -> str:
    """
    Traverse the code graph from a starting node.
    
    Use this tool to walk the graph and discover relationships:
    - Follow callees to see what a function calls
    - Follow callers to see who calls a function
    
    Args:
        node_name: Starting node name (function/class name)
        direction: Traversal direction. "callees" or "callers". Default: "callees"
        max_depth: Maximum traversal depth. Default: 3
        max_nodes: Maximum nodes to return. Default: 50
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with traversal results or error message.
        
    Examples:
        # See what process_payment calls (up to 3 levels deep)
        crg_traverse("process_payment", direction="callees")
        
        # See who calls the auth module (up to 5 levels)
        crg_traverse("authenticate", direction="callers", max_depth=5)
    """
    if direction not in ["callees", "callers"]:
        return "Error: direction must be 'callees' or 'callers'"
    
    cmd_args = (
        f'traverse "{node_name}" '
        f'--direction {direction} '
        f'--max-depth {max_depth} '
        f'--max-nodes {max_nodes}'
    )
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 5: Impact Analysis Tools

**File**: `src/liteagent/tools/code_review/impact.py`

```python
"""
Impact analysis tools for code-review-graph.
"""
from typing import Optional, List
from .executor import CRGExecutor


async def crg_impact(
    files: Optional[List[str]] = None,
    depth: int = 3,
    format: str = "json"
) -> str:
    """
    Analyze the blast radius of changes.
    
    Use this tool to understand what will be affected by changes:
    - Auto-detect changed files from git, or
    - Specify files manually
    
    Args:
        files: List of file paths to analyze. If None, auto-detect from git.
        depth: Maximum analysis depth. Default: 3
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with impact analysis or error message.
        
    Examples:
        # Analyze impact of all uncommitted changes
        crg_impact()
        
        # Analyze impact of specific files
        crg_impact(files=["src/auth.py", "src/user.py"])
        
        # Deep analysis (5 levels)
        crg_impact(depth=5)
    """
    cmd_args = f"impact --depth {depth}"
    
    if files:
        files_str = ",".join(files)
        cmd_args += f' --files "{files_str}"'
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_affected_flows(
    files: Optional[List[str]] = None,
    format: str = "json"
) -> str:
    """
    Find which execution flows are affected by changes.
    
    Use this tool to understand which code paths will be impacted by changes.
    
    Args:
        files: List of file paths to analyze. If None, auto-detect from git.
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with affected flows or error message.
        
    Examples:
        # Find affected flows from git changes
        crg_affected_flows()
        
        # Find flows affected by auth.py changes
        crg_affected_flows(files=["src/auth.py"])
    """
    cmd_args = "affected-flows"
    
    if files:
        files_str = ",".join(files)
        cmd_args += f' --files "{files_str}"'
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 6: Flow Tools

**File**: `src/liteagent/tools/code_review/flows.py`

```python
"""
Flow tools for code-review-graph.
"""
from typing import Optional
from .executor import CRGExecutor


async def crg_flows(
    limit: int = 20,
    sort: str = "criticality",
    kind: Optional[str] = None,
    format: str = "json"
) -> str:
    """
    List execution flows sorted by criticality.
    
    Use this tool to see the most important execution paths in the codebase.
    
    Args:
        limit: Maximum number of flows to return. Default: 20
        sort: Sort criteria. One of: criticality, depth, node_count. Default: criticality
        kind: Filter by entry point kind (e.g., Test). Optional.
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with flow list or error message.
        
    Examples:
        # Get top 10 most critical flows
        crg_flows(limit=10)
        
        # Get flows sorted by depth
        crg_flows(sort="depth")
        
        # Get test flows only
        crg_flows(kind="Test")
    """
    valid_sorts = ["criticality", "depth", "node_count"]
    if sort not in valid_sorts:
        return f"Error: sort must be one of: {', '.join(valid_sorts)}"
    
    cmd_args = f"flows --limit {limit} --sort {sort}"
    
    if kind:
        cmd_args += f" --kind {kind}"
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_flow(
    identifier: str,
    include_source: bool = False,
    format: str = "json"
) -> str:
    """
    Get details of a specific execution flow.
    
    Use this tool to examine a specific flow in detail.
    
    Args:
        identifier: Flow ID (number) or name (partial match)
        include_source: Include source code in output. Default: False
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with flow details or error message.
        
    Examples:
        # Get flow by ID
        crg_flow("1")
        
        # Get flow by name
        crg_flow("login")
        
        # Get flow with source code
        crg_flow("1", include_source=True)
    """
    cmd_args = f'flow "{identifier}"'
    
    if include_source:
        cmd_args += " --source"
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 7: Community Tools

**File**: `src/liteagent/tools/code_review/communities.py`

```python
"""
Community tools for code-review-graph.
"""
from typing import Optional
from .executor import CRGExecutor


async def crg_communities(
    sort: str = "criticality",
    format: str = "json"
) -> str:
    """
    List detected code communities (modules/groups).
    
    Use this tool to understand how the codebase is organized into logical groups.
    
    Args:
        sort: Sort criteria. One of: criticality, size. Default: criticality
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with community list or error message.
        
    Examples:
        # List communities by criticality
        crg_communities()
        
        # List communities by size
        crg_communities(sort="size")
    """
    valid_sorts = ["criticality", "size"]
    if sort not in valid_sorts:
        return f"Error: sort must be one of: {', '.join(valid_sorts)}"
    
    result = await CRGExecutor.execute(
        f"communities --sort {sort}",
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_community(
    name: str,
    include_members: bool = False,
    format: str = "json"
) -> str:
    """
    Get details of a specific code community.
    
    Use this tool to examine a specific community in detail.
    
    Args:
        name: Community name (from crg_communities)
        include_members: Include list of member nodes. Default: False
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with community details or error message.
        
    Examples:
        # Get community details
        crg_community("authentication")
        
        # Get community with member list
        crg_community("authentication", include_members=True)
    """
    cmd_args = f'community "{name}"'
    
    if include_members:
        cmd_args += " --members"
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_architecture(
    format: str = "markdown"
) -> str:
    """
    Get high-level architecture overview.
    
    Use this tool to understand the overall structure of the codebase.
    
    Args:
        format: Output format (json, table, markdown). Default: markdown
    
    Returns:
        Architecture overview or error message.
        
    Examples:
        # Get architecture overview
        crg_architecture()
    """
    result = await CRGExecutor.execute("architecture", format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 8: Analysis Tools

**File**: `src/liteagent/tools/code_review/analysis.py`

```python
"""
Analysis tools for code-review-graph.
"""
from typing import Optional
from .executor import CRGExecutor


async def crg_hubs(
    limit: int = 20,
    format: str = "json"
) -> str:
    """
    Find architectural hotspots (most connected nodes).
    
    Use this tool to identify the most important/frequently-used code elements.
    
    Args:
        limit: Maximum number of hubs to return. Default: 20
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with hub list or error message.
        
    Examples:
        # Find top 10 hubs
        crg_hubs(limit=10)
    """
    result = await CRGExecutor.execute(
        f"hubs --limit {limit}",
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_bridges(
    limit: int = 20,
    format: str = "json"
) -> str:
    """
    Find architectural chokepoints (nodes connecting communities).
    
    Use this tool to identify code that connects different modules - 
    these are critical for understanding dependencies.
    
    Args:
        limit: Maximum number of bridges to return. Default: 20
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with bridge list or error message.
        
    Examples:
        # Find top 10 bridges
        crg_bridges(limit=10)
    """
    result = await CRGExecutor.execute(
        f"bridges --limit {limit}",
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_gaps(
    format: str = "json"
) -> str:
    """
    Identify structural weaknesses in the codebase.
    
    Use this tool to find potential issues like:
    - Missing tests
    - Dead code
    - Unusual patterns
    
    Args:
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with gap analysis or error message.
        
    Examples:
        # Find structural gaps
        crg_gaps()
    """
    result = await CRGExecutor.execute("gaps", format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_surprises(
    limit: int = 20,
    format: str = "json"
) -> str:
    """
    Find unexpected coupling in the codebase.
    
    Use this tool to discover surprising connections that might indicate:
    - Hidden dependencies
    - Potential refactoring opportunities
    - Architecture violations
    
    Args:
        limit: Maximum number of surprises to return. Default: 20
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with surprise list or error message.
        
    Examples:
        # Find unexpected couplings
        crg_surprises(limit=10)
    """
    result = await CRGExecutor.execute(
        f"surprises --limit {limit}",
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_questions(
    format: str = "json"
) -> str:
    """
    Get auto-generated review questions for the codebase.
    
    Use this tool to get suggested questions to consider when reviewing code.
    
    Args:
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with review questions or error message.
        
    Examples:
        # Get review questions
        crg_questions()
    """
    result = await CRGExecutor.execute("questions", format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 9: Refactoring Tools

**File**: `src/liteagent/tools/code_review/refactor.py`

```python
"""
Refactoring tools for code-review-graph.
"""
from typing import Optional
from .executor import CRGExecutor


async def crg_refactor(
    action: str,
    old_name: Optional[str] = None,
    new_name: Optional[str] = None,
    kind: Optional[str] = None,
    format: str = "json"
) -> str:
    """
    Refactoring assistance tools.
    
    Use this tool for refactoring operations:
    - Preview a rename operation
    - Find dead code
    - Get refactoring suggestions
    
    Args:
        action: Refactoring action. One of:
            - "rename": Preview a rename (requires old_name, new_name)
            - "dead-code": Find dead code
            - "suggest": Get refactoring suggestions
        old_name: Current name (for rename action)
        new_name: New name (for rename action)
        kind: Filter by kind for dead-code (Function, Class). Optional.
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with refactoring info or error message.
        
    Examples:
        # Preview renaming a function
        crg_refactor("rename", old_name="old_func", new_name="new_func")
        
        # Find dead code
        crg_refactor("dead-code")
        
        # Find dead functions only
        crg_refactor("dead-code", kind="Function")
        
        # Get refactoring suggestions
        crg_refactor("suggest")
    """
    valid_actions = ["rename", "dead-code", "suggest"]
    if action not in valid_actions:
        return f"Error: action must be one of: {', '.join(valid_actions)}"
    
    if action == "rename":
        if not old_name or not new_name:
            return "Error: rename action requires old_name and new_name"
        cmd_args = f"refactor rename {old_name} {new_name}"
    
    elif action == "dead-code":
        cmd_args = "refactor dead-code"
        if kind:
            valid_kinds = ["Function", "Class"]
            if kind not in valid_kinds:
                return f"Error: kind must be one of: {', '.join(valid_kinds)}"
            cmd_args += f" --kind {kind}"
    
    elif action == "suggest":
        cmd_args = "refactor suggest"
    
    result = await CRGExecutor.execute(cmd_args, format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_large_functions(
    min_lines: int = 50,
    kind: str = "Function",
    format: str = "json"
) -> str:
    """
    Find oversized functions or classes.
    
    Use this tool to identify code that might need refactoring due to size.
    
    Args:
        min_lines: Minimum lines threshold. Default: 50
        kind: Kind to search. "Function" or "Class". Default: Function
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with large function list or error message.
        
    Examples:
        # Find functions over 50 lines
        crg_large_functions()
        
        # Find classes over 100 lines
        crg_large_functions(min_lines=100, kind="Class")
    """
    valid_kinds = ["Function", "Class"]
    if kind not in valid_kinds:
        return f"Error: kind must be one of: {', '.join(valid_kinds)}"
    
    result = await CRGExecutor.execute(
        f"large-functions --min-lines {min_lines} --kind {kind}",
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 10: Management Tools

**File**: `src/liteagent/tools/code_review/management.py`

```python
"""
Management tools for code-review-graph.
"""
from typing import Optional, List
from .executor import CRGExecutor


async def crg_status(
    format: str = "json"
) -> str:
    """
    Check the status of the knowledge graph.
    
    Use this tool to verify if the graph is built and up to date.
    
    Args:
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with status info or error message.
        
    Examples:
        # Check graph status
        crg_status()
    """
    result = await CRGExecutor.execute("status", format=format)
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_build(
    timeout: int = 300,
    format: str = "json"
) -> str:
    """
    Build the knowledge graph from scratch.
    
    Use this tool to create a fresh graph. This may take a while for large codebases.
    
    Args:
        timeout: Build timeout in seconds. Default: 300 (5 minutes)
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with build result or error message.
        
    Examples:
        # Build the graph
        crg_build()
    """
    result = await CRGExecutor.execute(
        "build",
        timeout=timeout,
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


async def crg_update(
    files: Optional[List[str]] = None,
    timeout: int = 120,
    format: str = "json"
) -> str:
    """
    Update the knowledge graph incrementally.
    
    Use this tool to update the graph after code changes.
    Without files specified, auto-detects changes from git.
    
    Args:
        files: Specific files to update. If None, auto-detect from git.
        timeout: Update timeout in seconds. Default: 120 (2 minutes)
        format: Output format (json, table, markdown). Default: json
    
    Returns:
        JSON string with update result or error message.
        
    Examples:
        # Update from git changes
        crg_update()
        
        # Update specific files
        crg_update(files=["src/auth.py", "src/user.py"])
    """
    cmd_args = "update"
    
    if files:
        files_str = ",".join(files)
        cmd_args += f' --files "{files_str}"'
    
    result = await CRGExecutor.execute(
        cmd_args,
        timeout=timeout,
        format=format
    )
    
    if result["success"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"
```

### Phase 11: Tool Registration

**File**: `src/liteagent/tools/code_review/__init__.py`

```python
"""
Code Review Graph tools for LiteAgent.
"""
from .query import crg_query
from .search import crg_search
from .traverse import crg_traverse
from .impact import crg_impact, crg_affected_flows
from .flows import crg_flows, crg_flow
from .communities import crg_communities, crg_community, crg_architecture
from .analysis import crg_hubs, crg_bridges, crg_gaps, crg_surprises, crg_questions
from .refactor import crg_refactor, crg_large_functions
from .management import crg_status, crg_build, crg_update

__all__ = [
    # Query
    "crg_query",
    # Search
    "crg_search",
    # Traverse
    "crg_traverse",
    # Impact
    "crg_impact",
    "crg_affected_flows",
    # Flows
    "crg_flows",
    "crg_flow",
    # Communities
    "crg_communities",
    "crg_community",
    "crg_architecture",
    # Analysis
    "crg_hubs",
    "crg_bridges",
    "crg_gaps",
    "crg_surprises",
    "crg_questions",
    # Refactor
    "crg_refactor",
    "crg_large_functions",
    # Management
    "crg_status",
    "crg_build",
    "crg_update",
]
```

**File**: `src/liteagent/tools/registry.py` (modifications)

```python
# Add to existing imports
from .code_review import (
    crg_query, crg_search, crg_traverse,
    crg_impact, crg_affected_flows,
    crg_flows, crg_flow,
    crg_communities, crg_community, crg_architecture,
    crg_hubs, crg_bridges, crg_gaps, crg_surprises, crg_questions,
    crg_refactor, crg_large_functions,
    crg_status, crg_build, crg_update
)

# Add to SAMPLE_INPUTS
SAMPLE_INPUTS.update({
    "crg_query": {
        "query_type": "callers_of",
        "target": "process_payment"
    },
    "crg_search": {
        "query": "authentication",
        "kind": "Function"
    },
    "crg_traverse": {
        "node_name": "main",
        "direction": "callees"
    },
    "crg_impact": {
        "files": "['src/auth.py']"
    },
    # ... add more sample inputs
})

# Register all CRG tools
registry.register(crg_query)
registry.register(crg_search)
registry.register(crg_traverse)
registry.register(crg_impact)
registry.register(crg_affected_flows)
registry.register(crg_flows)
registry.register(crg_flow)
registry.register(crg_communities)
registry.register(crg_community)
registry.register(crg_architecture)
registry.register(crg_hubs)
registry.register(crg_bridges)
registry.register(crg_gaps)
registry.register(crg_surprises)
registry.register(crg_questions)
registry.register(crg_refactor)
registry.register(crg_large_functions)
registry.register(crg_status)
registry.register(crg_build)
registry.register(crg_update)
```

---

## Tool Summary Table

| Tool | Category | Description | Common Use Case |
|------|----------|-------------|-----------------|
| `crg_query` | Query | Query relationships | "Who calls this function?" |
| `crg_search` | Search | Semantic search | "Find auth code" |
| `crg_traverse` | Traverse | Graph traversal | "Trace execution flow" |
| `crg_impact` | Impact | Blast radius | "What's affected?" |
| `crg_affected_flows` | Impact | Affected flows | "Which tests affected?" |
| `crg_flows` | Flows | List flows | "Show critical paths" |
| `crg_flow` | Flows | Flow details | "Explain this flow" |
| `crg_communities` | Community | List communities | "Show modules" |
| `crg_community` | Community | Community details | "What's in auth module?" |
| `crg_architecture` | Community | Architecture | "System overview" |
| `crg_hubs` | Analysis | Hotspots | "Most used code" |
| `crg_bridges` | Analysis | Chokepoints | "Cross-module deps" |
| `crg_gaps` | Analysis | Weaknesses | "Find issues" |
| `crg_surprises` | Analysis | Unexpected | "Hidden coupling" |
| `crg_questions` | Analysis | Review help | "What to check?" |
| `crg_refactor` | Refactor | Refactoring | "Preview rename" |
| `crg_large_functions` | Refactor | Large code | "Find big functions" |
| `crg_status` | Management | Graph status | "Is graph ready?" |
| `crg_build` | Management | Build graph | "Create graph" |
| `crg_update` | Management | Update graph | "Refresh graph" |

---

## Testing Plan

### Unit Tests

1. **CRGExecutor Tests**
   - Test command execution
   - Test JSON parsing
   - Test error handling
   - Test timeout handling

2. **Individual Tool Tests**
   - Test each tool with valid inputs
   - Test error cases
   - Test output format

### Integration Tests

1. **End-to-End Tool Usage**
   - Build graph
   - Query relationships
   - Analyze impact
   - Search code

2. **Error Recovery**
   - Test with missing CLI
   - Test with corrupted graph
   - Test with invalid inputs

---

## Agent Usage Examples

### Example 1: Understanding Code Before Changes

```
User: "I need to modify the payment processing. What should I be aware of?"

Agent:
1. crg_search("payment")  # Find payment-related code
2. crg_query("callers_of", "process_payment")  # Who uses it?
3. crg_impact(files=["src/payment.py"])  # What's affected?
4. crg_affected_flows(files=["src/payment.py"])  # Which flows?
```

### Example 2: Code Review Preparation

```
User: "Help me review the auth module changes"

Agent:
1. crg_impact()  # Auto-detect changes
2. crg_questions()  # Get review questions
3. crg_communities()  # Understand structure
4. crg_hubs(limit=5)  # Key areas to focus
```

### Example 3: Refactoring Planning

```
User: "I want to refactor the UserService class"

Agent:
1. crg_query("callers_of", "UserService")  # Who uses it?
2. crg_refactor("rename", "UserService", "AccountService")  # Preview rename
3. crg_large_functions(kind="Class")  # Check size
4. crg_gaps()  # Find issues
```

### Example 4: Debugging

```
User: "There's an error in the checkout flow"

Agent:
1. crg_search("checkout")  # Find checkout code
2. crg_flow("checkout")  # Get flow details
3. crg_traverse("checkout", direction="callees")  # Trace execution
4. crg_query("tests_for", "checkout")  # Find related tests
```

---

## Future Enhancements

1. **Caching**: Cache results for repeated queries
2. **Batch Operations**: Combine multiple queries in one call
3. **Streaming Output**: Stream large results
4. **Progress Indicators**: Show progress for long operations
5. **Smart Suggestions**: Suggest relevant tools based on context

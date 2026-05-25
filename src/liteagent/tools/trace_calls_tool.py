import json
from .providers import ToolProviderFactory

def create_trace_calls_tool(providers: ToolProviderFactory):
    def trace_calls(symbol: str, direction: str = "both", depth: int = 3, max_nodes: int = 50) -> str:
        """
        Traces the execution flow of a specific function or class.
        Returns a JSON tree representing the call graph.
        
        Args:
            symbol: The exact name of the function, class, or method to trace.
            direction: 'callers' (who uses this), 'callees' (what this uses), or 'both'.
            depth: Maximum depth of the call graph to traverse (default 3).
            max_nodes: Maximum total nodes to return to prevent giant graphs.
        """
        try:
            depth = int(depth) if depth not in (None, "") else 3
            max_nodes = int(max_nodes) if max_nodes not in (None, "") else 50
            results = providers.insight.graph_store.trace_calls(symbol, direction, depth, max_nodes)
            return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error tracing calls: {str(e)}"
    return trace_calls

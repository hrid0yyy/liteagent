import json
from .providers import ToolProviderFactory

def create_trace_calls_tool(providers: ToolProviderFactory):
    def trace_calls(symbol: str, direction: str = "both", depth: int = 3, max_nodes: int = 50) -> str:
        """
        Traverses the AST call graph.
        'callers' shows what relies on or uses the symbol.
        'callees' shows what the symbol uses.
        """
        try:
            results = providers.insight.graph_store.trace_calls(symbol, direction, depth, max_nodes)
            return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error tracing calls: {str(e)}"
    return trace_calls

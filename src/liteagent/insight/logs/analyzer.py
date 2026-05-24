from typing import List, Dict, Any

class LogAnalyzer:
    """Analyzes parsed logs for patterns, anomalies, and insights."""
    def __init__(self, log_index):
        self.log_index = log_index

    def get_recent_errors(self, path: str = "auto", last_hours: int = 24, include_stats: bool = True) -> Dict[str, Any]:
        """Groups and de-duplicates all recent [ERROR] or [FATAL] logs."""
        errors = self.log_index.get_recent_errors(last_hours)
        groups = {}
        for err in errors:
            msg = err["message"]
            if "Connection reset" in msg:
                key = "Connection reset"
            elif "Main loop exception" in msg:
                key = "Main loop exception"
            else:
                key = msg
            groups[key] = groups.get(key, 0) + 1
            
        group_list = [{"pattern": k, "count": v} for k, v in groups.items()]
        return {
            "total_errors": len(errors),
            "groups": group_list
        }

    def trace_error_to_code(self, error_string: str, graph_store) -> str:
        """Cross-references error string with the AST logged_errors index."""
        # Check if the graph store can find this error snippet
        result = graph_store.find_symbol_by_snippet(error_string)
        if result:
            return f"Found error in {result['file_path']}:{result['line']} inside {result['qualified_name']}\nCode context:\n{result['code']}"
        return f"Could not find code throwing error: {error_string}"

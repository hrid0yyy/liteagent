from typing import Optional
from .providers import ToolProviderFactory

def create_search_logs_tool(providers: ToolProviderFactory):
    def search_logs(query: str, is_plain: bool = True, context_lines: int = 2, level: Optional[str] = None, last_hours: Optional[int] = None, error_code: Optional[str] = None, limit: int = 50) -> str:
        """
        Queries the FTS5 log index.
        Use is_plain=True for instant keyword/error code lookup.
        Use is_plain=False for Python Regex directly against raw log lines.
        context_lines controls how many lines before and after the match are returned.
        """
        try:
            results = providers.insight.log_index.search(query, is_plain, context_lines, level, last_hours, error_code, limit)
            if not results:
                return f"No logs found matching query: {query}"
            
            output = []
            for r in results:
                output.append(f"[{r.get('timestamp', 'UNKNOWN')}] {r.get('level', 'INFO')} - Line {r.get('line_number', '?')} - {r.get('file_path', 'unknown')}\nContext:\n{r.get('context', '')}\n---")
            return "\n".join(output)
        except Exception as e:
            return f"Error searching logs: {str(e)}"
    return search_logs

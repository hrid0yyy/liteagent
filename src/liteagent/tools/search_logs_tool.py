from typing import Optional
from .providers import ToolProviderFactory

def create_search_logs_tool(providers: ToolProviderFactory):
    def search_logs(query: str, is_plain: bool = True, context_lines: int = 2, level: Optional[str] = None, last_hours: Optional[int] = None, error_code: Optional[str] = None, limit: int = 50) -> str:
        """
        Searches through application log files for errors, keywords, or patterns.
        
        Args:
            query: The search term or pattern to look for.
            is_plain: True for simple keyword matching, False for Python regex matching.
            context_lines: Number of surrounding lines to include before and after the match.
            level: Filter by log severity (e.g. 'ERROR', 'WARN', 'INFO').
            last_hours: Filter to logs within the last N hours.
            error_code: Filter by a specific error code if applicable.
            limit: Maximum number of matches to return.
        """
        try:
            if isinstance(is_plain, str):
                is_plain = is_plain.lower() in ('true', '1', 'yes', 't') if is_plain else True
            context_lines = int(context_lines) if context_lines not in (None, "") else 2
            last_hours = int(last_hours) if last_hours not in (None, "") else None
            limit = int(limit) if limit not in (None, "") else 50
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

from typing import Optional
from .providers import ToolProviderFactory

MAX_LIMIT = 5
DEFAULT_LIMIT = 1
MAX_CONTEXT_LINES = 5

def create_search_logs_tool(providers: ToolProviderFactory):
    def search_logs(query: str, is_plain: bool = True, context_lines: int = 2, last_hours: Optional[int] = None, limit: int = DEFAULT_LIMIT) -> str:
        """
        Searches through application log files for errors, keywords, or patterns.
        
        Args:
            query: The search term or pattern to look for.
            is_plain: True for simple keyword matching, False for Python regex matching.
            context_lines: Number of surrounding lines to include before and after the match. Default is 2, maximum is 5.
            last_hours: Filter to logs within the last N hours.
            limit: Maximum number of matches to return. Default is 1, maximum is 5.
        """
        warnings = []
        try:
            if isinstance(is_plain, str):
                is_plain = is_plain.lower() in ('true', '1', 'yes', 't') if is_plain else True
            context_lines = int(context_lines) if context_lines not in (None, "") else 2
            if context_lines > MAX_CONTEXT_LINES:
                warnings.append(f"context_lines cannot be greater than {MAX_CONTEXT_LINES}. Value was clamped from {context_lines} to {MAX_CONTEXT_LINES}.")
                context_lines = MAX_CONTEXT_LINES
            last_hours = int(last_hours) if last_hours not in (None, "") else None
            limit = int(limit) if limit not in (None, "") else DEFAULT_LIMIT
            if limit < 1:
                limit = 1
            if limit > MAX_LIMIT:
                warnings.append(f"limit cannot be greater than {MAX_LIMIT}. Value was clamped from {limit} to {MAX_LIMIT}.")
                limit = MAX_LIMIT
            results = providers.insight.log_index.search(query, is_plain, context_lines, last_hours, limit)
            if not results:
                return f"No logs found matching query: {query}"
            
            output = []
            for r in results:
                note = " [fuzzy match]" if r.get("fuzzy") else ""
                output.append(f"[{r.get('timestamp', 'UNKNOWN')}] {r.get('level', 'INFO')} - Line {r.get('line_number', '?')} - {r.get('file_path', 'unknown')}{note}\nContext:\n{r.get('context', '')}\n---")
            result_str = "\n".join(output)
            if warnings:
                result_str += "\n\n⚠ CONSTRAINT VIOLATION: " + " | ".join(warnings)
            return result_str
        except Exception as e:
            return f"Error searching logs: {str(e)}"
    return search_logs

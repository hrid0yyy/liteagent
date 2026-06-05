from typing import Optional
from .providers import ToolProviderFactory

MAX_LIMIT = 5
DEFAULT_LIMIT = 1
MAX_CONTEXT_LINES = 5

def create_search_logs_tool(providers: ToolProviderFactory):
    def search_logs(query: str, is_plain: bool = True, context_lines: int = 2, last_hours: Optional[int] = None, limit: int = DEFAULT_LIMIT, force: bool = False) -> str:
        """
        Searches through application log files for errors, keywords, or patterns.
        
        Args:
            query: The search term or pattern to look for.
            is_plain: True for simple keyword matching, False for Python regex matching.
            context_lines: Number of surrounding lines to include before and after the match. Default is 2, maximum is 5.
            last_hours: Filter to logs within the last N hours.
            limit: Maximum number of matches to return. Default is 1, maximum is 5.
            force: Bypass pre-search verification. Use when you believe the query is valid despite verification failure. Default is false.
        """
        warnings = []
        try:
            if isinstance(is_plain, str):
                is_plain = is_plain.lower() in ('true', '1', 'yes', 't') if is_plain else True
            if isinstance(force, str):
                force = force.lower() in ('true', '1', 'yes', 't') if force else False
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
            results = providers.insight.log_index.search(query, is_plain, context_lines, last_hours, limit, force=force)
            if not results:
                return f"No logs found matching query: {query}"
            
            # Handle verification blocked response
            if results and len(results) == 1 and results[0].get("verification_blocked"):
                return results[0]["message"]
            
            # Get graph_store for possible source matching
            graph_store = providers.insight.graph_store if hasattr(providers, 'insight') and providers.insight else None

            output = []
            for r in results:
                note = " [fuzzy match]" if r.get("fuzzy") else ""
                entry = f"[{r.get('timestamp', 'UNKNOWN')}] {r.get('level', 'INFO')} - Line {r.get('line_number', '?')} - {r.get('file_path', 'unknown')}{note}\nContext:\n{r.get('context', '')}"
                
                # Find possible source methods from knowledge graph
                if graph_store:
                    log_message = r.get("message", "")
                    sources = graph_store.find_matching_templates(log_message)
                    if sources:
                        source_lines = []
                        for s in sources:
                            fp = s["file_path"]
                            method = s["method_name"]
                            if "start_line" in s and "end_line" in s:
                                source_lines.append(f"  • {fp} → {method}() [lines {s['start_line']}-{s['end_line']}]")
                            else:
                                source_lines.append(f"  • {fp} → {method}()")
                        entry += "\nPossible sources:\n" + "\n".join(source_lines)
                
                entry += "\n---"
                output.append(entry)
            result_str = "\n".join(output)
            if warnings:
                result_str += "\n\n⚠ CONSTRAINT VIOLATION: " + " | ".join(warnings)
            return result_str
        except Exception as e:
            return f"Error searching logs: {str(e)}"
    return search_logs

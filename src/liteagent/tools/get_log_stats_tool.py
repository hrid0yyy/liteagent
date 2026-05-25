from pathlib import Path
from typing import Optional
from .providers import ToolProviderFactory

def create_get_log_stats_tool(providers: ToolProviderFactory):
    def get_log_stats(module: Optional[str] = None, level: Optional[str] = None, last_hours: int = 24) -> str:
        """
        Analyzes log frequencies to identify spammy logs or recurring issues.
        It groups log entries by their source code template and counts occurrences.
        Returns a statistical summary of log occurrences.
        
        Args:
            module: Optional file name or class name to filter templates (e.g. 'auth_service.py').
            level: Optional severity level to filter templates (e.g. 'ERROR', 'WARN').
            last_hours: Calculate stats only for logs from the last N hours.
        """
        try:
            last_hours = int(last_hours)
            templates = providers.insight.graph_store.get_log_templates(module, level)
            if not templates:
                return f"No log templates found in codebase for module={module}, level={level}."
                
            stats = {}
            for t in templates:
                query = t["template"]
                results = providers.insight.log_index.search(query, is_plain=False, limit=10000)
                
                if results:
                    stats[query] = {
                        "count": len(results),
                        "level": t["level"],
                        "file": Path(t["file_path"]).name,
                        "method": t["method_name"]
                    }
                
            if not stats:
                return f"All {len(templates)} extracted log templates returned 0 occurrences. System healthy."
                
            output = [f"Log Statistics for module={module}, level={level}:"]
            for template, data in stats.items():
                output.append(f"- [{data['level']}] {template} -> Found in: {data['file']}::{data['method']} | Occurrences: {data['count']}")
            return "\n".join(output)
        except Exception as e:
            return f"Error getting log stats: {str(e)}"
    return get_log_stats

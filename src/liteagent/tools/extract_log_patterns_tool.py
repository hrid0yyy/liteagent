
import re
from pathlib import Path
from typing import Optional
from collections import defaultdict
from .providers import ToolProviderFactory


def _regex_template_to_readable(template: str) -> str:
    """Convert a regex template from the AST parser back to readable format.
    e.g. '\\[APP\\] Command line args: (.*?)' → '[APP] Command line args: {...}'
    """
    # Replace (.*?) with {...}
    result = template.replace('(.*?)', '{...}')
    # Unescape regex special characters: \[ → [, \] → ], \. → ., etc.
    result = re.sub(r'\\(.)', r'\1', result)
    return result


def create_extract_log_patterns_tool(providers: ToolProviderFactory):
    def extract_log_patterns() -> str:
        """
        Extracts all log message templates from the codebase, grouped by file and method. Shows the full file path, method name with line range, and each log template with its level. Also populates the pre-search verification system for search_logs.
        """
        graph_store = providers.insight.graph_store if hasattr(providers, 'insight') and providers.insight else None
        if not graph_store:
            return "Error: Insight system not available. Cannot extract log patterns."

        # Get all log templates from the knowledge graph
        all_templates = graph_store.get_log_templates()
        if not all_templates:
            return "No log patterns found in the codebase. Make sure C# files have been indexed."

        # Get all methods for line range info
        # Collect unique file paths from templates
        file_paths = sorted(set(t["file_path"] for t in all_templates))

        # Build method lookup: file_path → list of methods with line ranges
        method_lookup = {}
        for fp in file_paths:
            method_lookup[fp] = graph_store.get_methods_for_file(fp)

        # Group templates by file_path → method_name
        file_method_groups = defaultdict(lambda: defaultdict(list))
        for t in all_templates:
            file_method_groups[t["file_path"]][t["method_name"]].append({
                "level": t["level"],
                "template": t["template"],
            })

        # Build output
        output_lines = []
        total_count = len(all_templates)

        for fp in file_paths:
            methods = file_method_groups[fp]
            output_lines.append(fp)

            # Build method line range lookup for this file
            method_ranges = {}
            for m in method_lookup.get(fp, []):
                method_ranges[m["name"]] = m

            for method_name, templates in methods.items():
                # Get method line range
                m_info = method_ranges.get(method_name)
                if m_info:
                    range_str = f"[lines {m_info['start_line']}-{m_info['end_line']}]"
                    display_name = f"Method: {method_name}() {range_str}"
                else:
                    display_name = f"{method_name}()"

                output_lines.append(f"  {display_name}")
                for t in templates:
                    readable = _regex_template_to_readable(t["template"])
                    output_lines.append(f"    {t['level']}: \"{readable}\"")

            output_lines.append("")

        # Store readable messages in LogIndex for pre-search verification
        log_index = providers.insight.log_index if hasattr(providers, 'insight') and providers.insight else None
        if log_index:
            readable_messages = [_regex_template_to_readable(t["template"]) for t in all_templates]
            log_index.set_known_log_messages(readable_messages)

        header = f"Found {total_count} log patterns in {len(file_paths)} files:\n"
        output_lines.insert(0, header)

        return "\n".join(output_lines).rstrip()

    return extract_log_patterns

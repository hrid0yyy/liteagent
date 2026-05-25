import re
from .providers import ToolProviderFactory

def create_trace_log_to_code_tool(providers: ToolProviderFactory):
    def trace_log_to_code(log_string: str) -> str:
        """
        Finds the exact source code location that generated a specific log message.
        
        Args:
            log_string: The exact log message string (or a large portion of it) from the logs.
        """
        try:
            templates = providers.insight.graph_store.get_log_templates()
            
            matched_template = None
            for t in templates:
                pattern = t["template"]
                try:
                    if re.search(pattern, log_string):
                        matched_template = t
                        break
                except re.error:
                    continue
                    
            if not matched_template:
                return "This log does not match any extracted templates from the codebase. It may originate from a third-party dependency or the AST index is outdated."
                
            cursor = providers.insight.graph_store.conn.cursor()
            cursor.execute("SELECT start_line, end_line, source_code FROM symbols WHERE file_path COLLATE NOCASE = ? AND name = ?", 
                          (matched_template["file_path"], matched_template["method_name"]))
            row = cursor.fetchone()
            
            output = [
                f"Log successfully traced!",
                f"File: {matched_template['file_path']}",
                f"Method: {matched_template['method_name']}",
                f"Level: {matched_template['level']}"
            ]
            
            if row:
                output.append(f"Line: {row[0]}-{row[1]}")
                output.append(f"Source Code:\n{row[2]}")
            else:
                output.append("Source code snippet could not be retrieved.")
                
            return "\n".join(output)
        except Exception as e:
            return f"Error tracing log to code: {str(e)}"
    return trace_log_to_code

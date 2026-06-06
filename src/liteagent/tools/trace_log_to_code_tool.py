import json
from pathlib import Path
from rapidfuzz import fuzz
from .providers import ToolProviderFactory

def create_trace_log_to_code_tool(providers: ToolProviderFactory):
    def trace_log_to_code(log_line: str) -> str:
        """
        Takes a raw log string and returns the exact source code method(s) that emitted it, including the file path and line numbers.
        
        Args:
            log_line: The specific log message string found in the runtime logs.
        """
        try:
            logbase_path = Path(providers.project_dir) / ".liteagent" / "logbase.json"
            if not logbase_path.exists():
                return "Error: logbase.json not found. Run /extractlogs first."
            
            with open(logbase_path, "r", encoding="utf-8") as f:
                logbase = json.load(f)
                
            matches = []
            
            for file_path, classes in logbase.items():
                for class_name, methods in classes.items():
                    if class_name == "_meta": continue
                    for method_name, method_info in methods.items():
                        best_score = 0
                        matched_template = ""
                        for tmpl in method_info.get("log_lines", []):
                            score = fuzz.partial_ratio(log_line.lower(), tmpl.lower())
                            if score > best_score:
                                best_score = score
                                matched_template = tmpl
                        
                        if best_score >= 65:
                            matches.append({
                                "file": file_path,
                                "class": class_name,
                                "method": method_name,
                                "line_range": method_info.get("line_range", "unknown"),
                                "score": best_score,
                                "template": matched_template
                            })
                            
            if not matches:
                return "No matching source code found for this log line."
                
            # Sort by score desc
            matches.sort(key=lambda x: x["score"], reverse=True)
            
            best = matches[0]
            output = [f"[BEST MATCH] (Score: {best['score']}%)"]
            output.append(f"File: {best['file']}")
            output.append(f"Class: {best['class']}")
            output.append(f"Method: {best['method']}")
            output.append(f"Line Range: {best['line_range']}")
            output.append(f"Matched Template: \"{best['template']}\"")
            
            if len(matches) > 1:
                output.append("\n[OTHER POTENTIAL MATCHES]")
                for i, m in enumerate(matches[1:4]): # top 3 others
                    output.append(f"{i+1}. (Score: {m['score']}%)")
                    output.append(f"File: {m['file']}")
                    output.append(f"Class: {m['class']}")
                    output.append(f"Method: {m['method']}")
                    output.append(f"Line Range: {m['line_range']}")
                    output.append(f"Matched Template: \"{m['template']}\"")
                    output.append("")
                    
            return "\n".join(output)
            
        except Exception as e:
            return f"Error tracing log: {str(e)}"
            
    return trace_log_to_code

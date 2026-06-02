from pathlib import Path
from typing import List, Optional
from .providers import ToolProviderFactory

DEFAULT_READ_LINES = 100

def create_read_file_tool(providers: ToolProviderFactory):
    def read_file(file_paths: List[str], start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """Reads one or more files, optionally within a specific line range, prepending line numbers. Do NOT use this tool to read log files; use read_log_lineRange instead. If no line range is specified, reads the first 100 lines by default."""
        start_line = int(start_line) if start_line not in (None, "") else None
        end_line = int(end_line) if end_line not in (None, "") else None
        all_output = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                all_output.append(f"Error: File {file_path} does not exist.")
                continue
            
            try:
                raw_content = path.read_text(encoding="utf-8")
                lines = raw_content.splitlines()
                
                # Default: if no range specified, read first 100 lines
                if start_line is None and end_line is None:
                    start = 0
                    end = min(DEFAULT_READ_LINES, len(lines))
                else:
                    start = (start_line - 1) if start_line else 0
                    end = end_line if end_line else len(lines)
                
                selected_lines = lines[start:end]
                
                numbered_lines = [f"{i + 1 + start}: {line}" for i, line in enumerate(selected_lines)]
                content = "\n".join(numbered_lines)

                is_full_read = start == 0 and end >= len(lines)
                providers.container.read_tracker.record_read(str(path), raw_content, is_full_read=is_full_read)
                
                all_output.append(f"--- {file_path} (Lines {start+1}-{end}) ---\n{content}\n--- End of selection ---")
            except Exception as e:
                all_output.append(f"Error reading {file_path}: {str(e)}")
                
        return "\n\n".join(all_output)
    return read_file

from pathlib import Path
from typing import Optional
from itertools import islice
from .providers import ToolProviderFactory

MAX_RANGE = 5
DEFAULT_RANGE = 3

def create_read_log_lineRange_tool(providers: ToolProviderFactory):
    def read_log_lineRange(path: str, startLine: int, range: int = DEFAULT_RANGE) -> str:
        """
        Reads a range of lines from a log file. Use this tool instead of read_file for log files.
        
        Args:
            path: The path to the log file to read.
            startLine: The 1-based line number to start reading from.
            range: Number of lines to read starting from startLine. Default is 3, maximum is 5.
        """
        warnings = []
        try:
            startLine = int(startLine) if startLine not in (None, "") else 1
            range = int(range) if range not in (None, "") else DEFAULT_RANGE

            # Clamp range and warn
            if range < 1:
                range = 1
            if range > MAX_RANGE:
                warnings.append(f"range cannot be greater than {MAX_RANGE}. Value was clamped from {range} to {MAX_RANGE}.")
                range = MAX_RANGE

            file_path = Path(path)
            if not file_path.exists():
                return f"Error: Log file {path} does not exist."

            if startLine < 1:
                startLine = 1

            start_idx = startLine - 1

            # Stream only the needed lines instead of loading the entire file
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                selected_lines = list(islice(f, start_idx, start_idx + range))

            # Strip newline characters
            selected_lines = [line.rstrip("\n").rstrip("\r") for line in selected_lines]

            if not selected_lines:
                return f"Error: No lines found in range (startLine={startLine}, range={range})."

            numbered_lines = [f"{i + 1 + start_idx}: {line}" for i, line in enumerate(selected_lines)]
            content = "\n".join(numbered_lines)

            end_line = startLine + len(selected_lines) - 1
            result_str = f"--- {path} (Lines {startLine}-{end_line}) ---\n{content}\n--- End of selection ---"
            if warnings:
                result_str += "\n\n⚠ CONSTRAINT VIOLATION: " + " | ".join(warnings)
            return result_str
        except Exception as e:
            return f"Error reading log file {path}: {str(e)}"
    return read_log_lineRange

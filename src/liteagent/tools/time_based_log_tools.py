import os
import re
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from .providers import ToolProviderFactory

# Flexible timestamp matcher: [2026-06-06 14:32:05] or 2026/06/06 14:32:05
TIMESTAMP_PATTERN = re.compile(r'(?:\[)?(\d{4}[-/]\d{2}[-/]\d{2}[\sT]\d{2}:\d{2}:\d{2})(?:\])?')

def extract_timestamp(line: str) -> Optional[datetime]:
    match = TIMESTAMP_PATTERN.search(line)
    if match:
        ts_str = match.group(1).replace('/', '-')
        try:
            return datetime.fromisoformat(ts_str.replace(' ', 'T'))
        except ValueError:
            pass
    return None

def create_get_log_time_bounds_tool(providers: ToolProviderFactory):
    def get_log_time_bounds(log_id_or_path: str) -> str:
        """
        Helps the agent understand the total chronological span of a given log file.
        
        Args:
            log_id_or_path: The ID of the log file from analyzer_config or its absolute path.
        """
        try:
            from ..core.analyzer_config import AnalyzerConfig
            config = AnalyzerConfig(providers.project_dir)
            logs = config.get_logs()
            
            file_path = logs.get(log_id_or_path, log_id_or_path)
            log_path = Path(file_path)
            
            if not log_path.exists():
                return f"Error: Log file not found at {file_path}"
                
            start_time = None
            end_time = None
            
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Find start
                for _ in range(100):
                    line = f.readline()
                    if not line: break
                    ts = extract_timestamp(line)
                    if ts:
                        start_time = ts
                        break
                        
                # Find end
                f.seek(0, os.SEEK_END)
                pos = f.tell()
                buffer_size = 4096
                lines = []
                while pos > 0 and not end_time:
                    read_size = min(buffer_size, pos)
                    pos -= read_size
                    f.seek(pos)
                    chunk = f.read(read_size)
                    lines = chunk.splitlines() + lines
                    
                    for line in reversed(lines):
                        ts = extract_timestamp(line)
                        if ts:
                            end_time = ts
                            break
                            
            if not start_time or not end_time:
                return "Could not extract clear start/end timestamps from the log file."
                
            duration = end_time - start_time
            
            import json
            return json.dumps({
                "log_file": str(log_path),
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_duration": str(duration)
            }, indent=2)
            
        except Exception as e:
            return f"Error getting time bounds: {str(e)}"
            
    return get_log_time_bounds

def create_read_log_time_range_tool(providers: ToolProviderFactory):
    def read_log_time_range(log_id_or_path: str, start_time: str, span_seconds: int = 60) -> str:
        """
        Allows the agent to zoom into a specific slice of time in the logs.
        
        Args:
            log_id_or_path: The target log file ID or path.
            start_time: The target start time (e.g., "2026-06-06 14:30:00" or "14:30:00"). If date is omitted, it attempts to use the file's primary date.
            span_seconds: How many seconds of logs to return after the start_time. Defaults to 60.
        """
        try:
            from ..core.analyzer_config import AnalyzerConfig
            config = AnalyzerConfig(providers.project_dir)
            logs = config.get_logs()
            
            file_path = logs.get(log_id_or_path, log_id_or_path)
            log_path = Path(file_path)
            
            if not log_path.exists():
                return f"Error: Log file not found at {file_path}"
                
            try:
                target_start = datetime.fromisoformat(start_time.replace(' ', 'T'))
            except ValueError:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for _ in range(100):
                        ts = extract_timestamp(f.readline())
                        if ts:
                            date_str = ts.strftime("%Y-%m-%d")
                            target_start = datetime.fromisoformat(f"{date_str}T{start_time}")
                            break
                    else:
                        return "Error: Invalid start_time format. Use YYYY-MM-DD HH:MM:SS"
                        
            target_end = target_start + timedelta(seconds=int(span_seconds))
            
            output_lines = []
            current_ts = None
            
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line_ts = extract_timestamp(line)
                    if line_ts:
                        current_ts = line_ts
                        
                    if not current_ts:
                        continue
                        
                    if current_ts >= target_start and current_ts <= target_end:
                        output_lines.append(line.rstrip())
                    elif current_ts > target_end:
                        break 
                        
            if not output_lines:
                return f"No logs found in the time window {target_start} to {target_end}"
                
            total_lines = len(output_lines)
            if total_lines > 10:
                truncated_count = total_lines - 10
                result = "\n".join(output_lines[:10])
                result += f"\n... ({truncated_count} more log lines were truncated)"
                return result
                
            return "\n".join(output_lines)
            
        except Exception as e:
            return f"Error reading log time range: {str(e)}"
            
    return read_log_time_range

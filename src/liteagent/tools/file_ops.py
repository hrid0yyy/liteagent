import os
from pathlib import Path
from typing import Optional

def read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Reads a file, optionally within a specific line range."""
    path = Path(file_path)
    if not path.exists():
        return f"Error: File {file_path} does not exist."
    
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        start = (start_line - 1) if start_line else 0
        end = end_line if end_line else len(lines)
        
        selected_lines = lines[start:end]
        content = "\n".join(selected_lines)
        return f"--- {file_path} (Lines {start+1}-{end}) ---\n{content}\n--- End of selection ---"
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

def write_file(file_path: str, content: str) -> str:
    """Writes content to a file, overwriting if it exists."""
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to {file_path}: {str(e)}"

def modify_file(file_path: str, old_string: str, new_string: str) -> str:
    """Surgically replaces exactly one occurrence of old_string with new_string."""
    path = Path(file_path)
    if not path.exists():
        return f"Error: File {file_path} does not exist."
    
    try:
        content = path.read_text(encoding="utf-8")
        count = content.count(old_string)
        
        if count == 0:
            # Provide more helpful feedback for failure
            return (f"Error: Could not find an exact match for the 'old_string' in {file_path}.\n"
                    f"TIP: Make sure you use 'read_file' first to see the EXACT text, including spacing and quotes.")
        
        if count > 1:
            return f"Error: Found {count} occurrences of 'old_string' in {file_path}. Please provide more surrounding context to ensure a unique match."
        
        new_content = content.replace(old_string, new_string)
        path.write_text(new_content, encoding="utf-8")
        return f"Successfully modified {file_path}"
    except Exception as e:
        return f"Error modifying {file_path}: {str(e)}"

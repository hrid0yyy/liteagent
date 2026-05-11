import os
from pathlib import Path
from typing import List, Optional

def get_workspace_info(dir_path: str = ".", ignore_patterns: Optional[List[str]] = None) -> str:
    """ Lists the directory structure, respecting common ignore patterns. """
    output = []
    base_path = Path(dir_path).resolve()
    
    # Simple default ignore list
    default_ignore = {".git", "__pycache__", ".venv", "node_modules", ".DS_Store", ".pytest_cache"}
    if ignore_patterns:
        default_ignore.update(ignore_patterns)

    def _list_dir(current_path: Path, indent: str = ""):
        try:
            items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            for i, item in enumerate(items):
                if item.name in default_ignore:
                    continue
                
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                output.append(f"{indent}{connector}{item.name}{'/' if item.is_dir() else ''}")
                
                if item.is_dir():
                    new_indent = indent + ("    " if is_last else "│   ")
                    # Limit depth to avoid massive output
                    if len(new_indent) // 4 < 3: 
                        _list_dir(item, new_indent)
        except PermissionError:
            output.append(f"{indent} [Permission Denied]")

    output.append(f"Workspace: {base_path}")
    _list_dir(base_path)
    return "\n".join(output)

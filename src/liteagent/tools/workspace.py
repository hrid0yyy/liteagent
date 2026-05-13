import os
import re
import fnmatch
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


def _find_project_root(start_path: Path) -> Path:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current] + list(current.parents):
        if (candidate / ".git").exists():
            return candidate
    return Path.cwd().resolve()


def list_files(pattern: str = "**/*", dir_path: Optional[str] = None) -> str:
    """
    Lists files and directories matching a glob pattern.

    Args:
        pattern: Glob pattern to match (e.g., '**/*.py', '**/tests', '*').
        dir_path: Optional directory path to search from. If omitted, uses project root.
    """
    base_path = Path(dir_path).resolve() if dir_path else _find_project_root(Path.cwd())
    if not base_path.exists():
        return f"Error: Path does not exist: {base_path}"
    if not base_path.is_dir():
        return f"Error: Path is not a directory: {base_path}"

    matches = []
    try:
        for item in base_path.glob(pattern):
            if item == base_path:
                continue
            rel = item.relative_to(base_path).as_posix()
            matches.append(rel + ("/" if item.is_dir() else ""))
    except re.error as e:
        return f"Error: Invalid glob pattern - {e}"
    except Exception as e:
        return f"Error while listing files: {e}"

    if not matches:
        return f"No matches found for pattern: {pattern}"

    matches = sorted(set(matches))
    return "\n".join(matches)


def search_in_files(
    pattern: str,
    dir_path: str = ".",
    file_pattern: str = "**/*",
    ignore_patterns: Optional[List[str]] = None,
    literal: bool = False,
) -> str:
    """
    Searches within files matching a glob pattern using regex or literal text matching.
    
    Args:
        pattern: The regex pattern or literal text to search for.
        dir_path: The directory to start searching from (defaults to '.').
        file_pattern: Glob pattern to filter files (e.g., '**/*.py'). Defaults to '**/*'.
        ignore_patterns: Additional directories to ignore.
        literal: If True, treats pattern as plain text instead of regex.
    """
    base_path = Path(dir_path).resolve()
    
    # Common ignore sets
    default_ignore_dirs = {".git", "__pycache__", ".venv", "node_modules", ".DS_Store", ".pytest_cache"}
    if ignore_patterns:
        default_ignore_dirs.update(ignore_patterns)

    try:
        effective_pattern = re.escape(pattern) if literal else pattern
        regex = re.compile(effective_pattern)
    except re.error as e:
        return f"Error: Invalid regular expression pattern - {e}"

    results = []
    total_matches = 0
    max_matches = 100 # Safety limit
    
    for root, dirs, files in os.walk(base_path):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in default_ignore_dirs]
        
        for file in files:
            file_path = Path(root) / file
            
            # Match the file against the glob file_pattern relative to base_path
            try:
                rel_path = file_path.relative_to(base_path)
                # Convert rel_path to string with forward slashes for cross-platform globbing
                rel_path_str = rel_path.as_posix()
                if not fnmatch.fnmatch(rel_path_str, file_pattern):
                    continue
            except ValueError:
                continue

            try:
                # Try reading as text
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                
                file_matches = []
                for i, line in enumerate(lines):
                    if regex.search(line):
                        file_matches.append(f"{i + 1}: {line.strip()}")
                        total_matches += 1
                        
                if file_matches:
                    results.append(f"--- {rel_path} ---")
                    results.extend(file_matches)
                    results.append("")
                    
                if total_matches >= max_matches:
                    results.append(f"\n... Max matches ({max_matches}) reached. Truncating results.")
                    return "\n".join(results)
                    
            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                pass

    if not results:
        return f"No matches found for pattern: {pattern}"

    return "\n".join(results).strip()

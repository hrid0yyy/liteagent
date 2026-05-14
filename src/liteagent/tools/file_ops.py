import os
import re
import shutil
from pathlib import Path
from typing import Optional, List
from ..core.container import get_container

def read_file(file_paths: List[str], start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Reads one or more files, optionally within a specific line range, prepending line numbers."""
    all_output = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            all_output.append(f"Error: File {file_path} does not exist.")
            continue
        
        try:
            raw_content = path.read_text(encoding="utf-8")
            lines = raw_content.splitlines()
            start = (start_line - 1) if start_line else 0
            end = end_line if end_line else len(lines)
            
            selected_lines = lines[start:end]
            
            # Format with line numbers: '1: content'
            numbered_lines = [f"{i + 1 + start}: {line}" for i, line in enumerate(selected_lines)]
            content = "\n".join(numbered_lines)

            is_full_read = start == 0 and end >= len(lines)
            get_container().read_tracker.record_read(str(path), raw_content, is_full_read=is_full_read)
            
            all_output.append(f"--- {file_path} (Lines {start+1}-{end}) ---\n{content}\n--- End of selection ---")
        except Exception as e:
            all_output.append(f"Error reading {file_path}: {str(e)}")
            
    return "\n\n".join(all_output)

def write_file(file_path: str, content: str) -> str:
    """Writes content to a file, overwriting if it exists."""
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to {file_path}: {str(e)}"

def rename_path(old_path: str, new_path: str) -> str:
    """Renames a file or directory to a new path."""
    source = Path(old_path)
    target = Path(new_path)

    if not source.exists():
        return f"Error: Path {old_path} does not exist."

    if target.exists():
        return f"Error: Target path {new_path} already exists."

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        get_container().read_tracker.rename_tracked_path(str(source), str(target))
        item_type = "directory" if target.is_dir() else "file"
        return f"Successfully renamed {item_type} from {old_path} to {new_path}"
    except Exception as e:
        return f"Error renaming {old_path} to {new_path}: {str(e)}"


def delete_path(path_to_delete: str) -> str:
    """Deletes a file or directory. Directories are removed recursively."""
    path = Path(path_to_delete)

    if not path.exists():
        return f"Error: Path {path_to_delete} does not exist."

    try:
        if path.is_file():
            path.unlink()
            get_container().read_tracker.remove_tracked_path(str(path))
            return f"Successfully deleted file {path_to_delete}"
        if path.is_dir():
            shutil.rmtree(path)
            get_container().read_tracker.remove_tracked_path(str(path))
            return f"Successfully deleted directory {path_to_delete}"
        return f"Error: Unsupported path type for {path_to_delete}"
    except Exception as e:
        return f"Error deleting {path_to_delete}: {str(e)}"


def modify_file(file_path: str, edits: str) -> str:
    """
    Applies batch edits to a file using SEARCH/REPLACE blocks.
    Format:
    >>> SEARCH
    old code
    +++ REPLACE
    new code
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File {file_path} does not exist."

    try:
        original_content = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

    # Parse SEARCH/REPLACE pairs
    pairs = []
    # Split by >>> SEARCH but skip the first empty part if it exists
    parts = edits.split(">>> SEARCH")
    for part in parts:
        if "+++ REPLACE" in part:
            sub_parts = part.split("+++ REPLACE")
            search_str = sub_parts[0].strip("\r\n")
            replace_str = sub_parts[1].strip("\r\n")
            if search_str:
                pairs.append((search_str, replace_str))

    if not pairs:
        return f"Error: No valid SEARCH/REPLACE pairs found for {file_path}"

    current_content = original_content

    def apply_one(content: str, search_string: str, replace_string: str):
        search_lines = search_string.splitlines()
        current_file_lines = content.splitlines()
        replace_lines = replace_string.splitlines()

        # 1) Strict line/block matching
        exact_match_start = -1
        exact_matches_found = 0
        for i in range(len(current_file_lines) - len(search_lines) + 1):
            window = current_file_lines[i : i + len(search_lines)]
            if window == search_lines:
                exact_match_start = i
                exact_matches_found += 1

        if exact_matches_found == 1:
            new_lines = current_file_lines[:exact_match_start]
            new_lines.extend(replace_lines)
            new_lines.extend(current_file_lines[exact_match_start + len(search_lines):])
            return "\n".join(new_lines), None

        if exact_matches_found > 1:
            return None, f"Error: Found {exact_matches_found} exact matches for a search block."

        # 2) Easy-going matching: allow indentation/whitespace differences
        def lines_match(f_line, s_line):
            return f_line.strip() == s_line.strip()

        best_match_start = -1
        matches_found = 0

        for i in range(len(current_file_lines) - len(search_lines) + 1):
            window = current_file_lines[i : i + len(search_lines)]
            if all(lines_match(w, s) for w, s in zip(window, search_lines)):
                best_match_start = i
                matches_found += 1

        if matches_found != 1:
            if matches_found > 1:
                return None, f"Error: Found {matches_found} similar matches for a search block."
            return None, f"Error: Could not find match for search block."

        new_lines = current_file_lines[:best_match_start]
        orig_first_line = current_file_lines[best_match_start]
        indent = re.match(r'^([ \t]*)', orig_first_line).group(1)

        search_first_line = search_lines[0]
        search_indent = re.match(r'^([ \t]*)', search_first_line).group(1)

        final_replace_lines = []
        for r_line in replace_lines:
            if r_line.startswith(search_indent):
                final_replace_lines.append(indent + r_line[len(search_indent):])
            else:
                final_replace_lines.append(r_line)

        new_lines.extend(final_replace_lines)
        new_lines.extend(current_file_lines[best_match_start + len(search_lines):])
        return "\n".join(new_lines), None

    # Apply all pairs
    for search_str, replace_str in pairs:
        updated, error = apply_one(current_content, search_str, replace_str)
        if error:
            return f"Error in {file_path}: {error}"
        current_content = updated

    # Handle trailing newline consistency
    if original_content.endswith("\n") and not current_content.endswith("\n"):
        current_content += "\n"

    if current_content != original_content:
        try:
            path.write_text(current_content, encoding="utf-8")
            return f"Successfully applied {len(pairs)} edit(s) to {file_path}"
        except Exception as e:
            return f"Error writing to {file_path}: {str(e)}"
    
    return f"No changes made to {file_path} (content already matches)."



import os
import re
from pathlib import Path
from typing import Optional, List

def read_file(file_paths: List[str], start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Reads one or more files, optionally within a specific line range, prepending line numbers."""
    all_output = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            all_output.append(f"Error: File {file_path} does not exist.")
            continue
        
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            start = (start_line - 1) if start_line else 0
            end = end_line if end_line else len(lines)
            
            selected_lines = lines[start:end]
            
            # Format with line numbers: '1: content'
            numbered_lines = [f"{i + 1 + start}: {line}" for i, line in enumerate(selected_lines)]
            content = "\n".join(numbered_lines)
            
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

def modify_file(edits: str) -> str:
    """
    Applies batch edits across files using custom markers.
    Format:
    >>> BEGIN
    >>> FILE : path/to/file.py
    >>> SEARCH
    old code
    +++ REPLACE
    new code
    >>> END
    """
    if ">>> BEGIN" not in edits or ">>> END" not in edits:
        return "Error: Missing >>> BEGIN or >>> END markers."

    try:
        content = edits.split(">>> BEGIN")[1].split(">>> END")[0].strip()
    except IndexError:
        return "Error: Could not parse content between >>> BEGIN and >>> END."

    file_blocks = content.split(">>> FILE : ")
    operations = []
    errors = []

    for block in file_blocks:
        if not block.strip():
            continue

        lines = block.splitlines()
        file_path = lines[0].strip()
        file_content_block = "\n".join(lines[1:])
        path = Path(file_path)

        if not path.exists():
            errors.append(f"Error: File {file_path} does not exist.")
            continue

        pairs = []
        search_parts = file_content_block.split(">>> SEARCH")
        for part in search_parts:
            if "+++ REPLACE" in part:
                sub_parts = part.split("+++ REPLACE")
                search_str = sub_parts[0].strip("\r\n")
                replace_str = sub_parts[1].strip("\r\n")
                pairs.append((search_str, replace_str))

        if not pairs:
            errors.append(f"Warning: No valid SEARCH/REPLACE pairs found for {file_path}")
            continue

        operations.append({"file_path": file_path, "path": path, "pairs": pairs})

    if errors:
        return "\n".join(errors)

    original_contents = {}
    working_contents = {}
    edits_per_file = {}

    for op in operations:
        file_path = op["file_path"]
        path = op["path"]
        if file_path in original_contents:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error modifying {file_path}: {str(e)}"
        original_contents[file_path] = original
        working_contents[file_path] = original
        edits_per_file[file_path] = 0

    def apply_one(current_content: str, file_path: str, search_string: str, replace_string: str):
        search_lines = search_string.splitlines()
        if not search_lines:
            return None, f"Error in {file_path}: search_string is empty."

        current_file_lines = current_content.splitlines()
        replace_lines = replace_string.splitlines()

        # 1) Strict line/block matching first (prevents substring edits like "1" inside "10")
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
            return None, f"Error in {file_path}: Found {exact_matches_found} exact matches for a search block."

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
                return None, f"Error in {file_path}: Found {matches_found} similar matches for a search block."
            return None, f"Error in {file_path}: Could not find match for search block."

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

    for op in operations:
        file_path = op["file_path"]
        temp_content = working_contents[file_path]
        for search_string, replace_string in op["pairs"]:
            updated, error = apply_one(temp_content, file_path, search_string, replace_string)
            if error:
                return error
            temp_content = updated
            edits_per_file[file_path] += 1
        working_contents[file_path] = temp_content

    results = []
    for file_path, original_content in original_contents.items():
        temp_content = working_contents[file_path]
        if original_content.endswith("\n") and not temp_content.endswith("\n"):
            temp_content += "\n"
        if temp_content != original_content:
            Path(file_path).write_text(temp_content, encoding="utf-8")
        results.append(f"Successfully applied {edits_per_file[file_path]} edit(s) to {file_path}")

    return "\n".join(results)



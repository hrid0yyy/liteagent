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

    # Extract everything between BEGIN and END
    try:
        content = edits.split(">>> BEGIN")[1].split(">>> END")[0].strip()
    except IndexError:
        return "Error: Could not parse content between >>> BEGIN and >>> END."
    
    # Split by file blocks
    file_blocks = content.split(">>> FILE : ")
    all_results = []

    for block in file_blocks:
        if not block.strip():
            continue
        
        # Extract path and the rest of the content
        lines = block.splitlines()
        file_path = lines[0].strip()
        file_content_block = "\n".join(lines[1:])
        
        path = Path(file_path)
        if not path.exists():
            all_results.append(f"Error: File {file_path} does not exist.")
            continue
            
        # Split search/replace pairs
        pairs = []
        search_parts = file_content_block.split(">>> SEARCH")
        for part in search_parts:
            if "+++ REPLACE" in part:
                sub_parts = part.split("+++ REPLACE")
                # Strip leading/trailing newlines from markers but preserve internal structure
                search_str = sub_parts[0].strip("\r\n")
                replace_str = sub_parts[1].strip("\r\n")
                pairs.append((search_str, replace_str))

        if not pairs:
            all_results.append(f"Warning: No valid SEARCH/REPLACE pairs found for {file_path}")
            continue

        try:
            original_content = path.read_text(encoding="utf-8")
            temp_content = original_content
            file_success = True
            file_edits_count = 0
            
            for search_string, replace_string in pairs:
                # Use Easy-Going Matching Logic
                # 1. Try Exact Match
                count = temp_content.count(search_string)
                if count == 1:
                    temp_content = temp_content.replace(search_string, replace_string)
                    file_edits_count += 1
                    continue
                
                # 2. Easy-going matching: Try to handle indentation/whitespace differences
                search_lines = search_string.strip().splitlines()
                if not search_lines:
                    all_results.append(f"Error in {file_path}: search_string is empty.")
                    file_success = False
                    break
                    
                current_file_lines = temp_content.splitlines()
                
                def lines_match(f_line, s_line):
                    return f_line.strip() == s_line.strip()

                best_match_start = -1
                matches_found = 0
                
                for i in range(len(current_file_lines) - len(search_lines) + 1):
                    window = current_file_lines[i : i + len(search_lines)]
                    if all(lines_match(w, s) for w, s in zip(window, search_lines)):
                        best_match_start = i
                        matches_found += 1
                
                if matches_found == 1:
                    new_lines = current_file_lines[:best_match_start]
                    replace_lines = replace_string.splitlines()
                    
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
                    
                    temp_content = "\n".join(new_lines)
                    file_edits_count += 1
                else:
                    if matches_found > 1:
                        all_results.append(f"Error in {file_path}: Found {matches_found} similar matches for a search block.")
                    else:
                        all_results.append(f"Error in {file_path}: Could not find match for search block.")
                    file_success = False
                    break

            if file_success and file_edits_count > 0:
                # Add trailing newline if the original file had one
                if original_content.endswith("\n") and not temp_content.endswith("\n"):
                    temp_content += "\n"
                path.write_text(temp_content, encoding="utf-8")
                all_results.append(f"Successfully applied {file_edits_count} edit(s) to {file_path}")
                
        except Exception as e:
            all_results.append(f"Error modifying {file_path}: {str(e)}")
            
    return "\n".join(all_results)



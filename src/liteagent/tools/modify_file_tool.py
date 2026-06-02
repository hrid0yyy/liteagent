import re
from pathlib import Path
from .providers import ToolProviderFactory

def create_modify_file_tool(providers: ToolProviderFactory):
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

        pairs = []
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

        for search_str, replace_str in pairs:
            updated, error = apply_one(current_content, search_str, replace_str)
            if error:
                return f"Error in {file_path}: {error}"
            current_content = updated

        if original_content.endswith("\n") and not current_content.endswith("\n"):
            current_content += "\n"

        if current_content != original_content:
            try:
                path.write_text(current_content, encoding="utf-8")
                return f"Successfully applied {len(pairs)} edit(s) to {file_path}"
            except Exception as e:
                return f"Error writing to {file_path}: {str(e)}"
        
        return f"No changes made to {file_path} (content already matches)."
    return modify_file

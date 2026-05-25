import re
from pathlib import Path
from typing import List, Optional
from .providers import ToolProviderFactory

def create_search_in_files_tool(providers: ToolProviderFactory):
    def _find_project_root(start_path: Path) -> Path:
        current = start_path.resolve()
        if current.is_file():
            current = current.parent
        for candidate in [current] + list(current.parents):
            if (candidate / ".git").exists():
                return candidate
        return Path.cwd().resolve()

    def search_in_files(pattern: str, dir_path: str = ".", file_pattern: str = "*", ignore_patterns: Optional[List[str]] = None, literal: bool = False) -> str:
        """ Searches for a string or regex pattern in files. """
        import fnmatch
        output = []
        base_path = Path(dir_path).resolve()
        
        if not base_path.exists():
            return f"Error: Directory {dir_path} does not exist."

        default_ignore = {".git", "__pycache__", ".venv", "node_modules", ".DS_Store", ".pytest_cache"}
        if ignore_patterns:
            default_ignore.update(ignore_patterns)

        if not literal:
            try:
                compiled_pattern = re.compile(pattern)
            except re.error as e:
                return f"Error compiling regex: {e}"

        def _should_ignore(p: Path) -> bool:
            rel_path = p.relative_to(base_path) if p.is_relative_to(base_path) else p
            for part in rel_path.parts:
                if part in default_ignore:
                    return True
            return False

        files_searched = 0
        matches_found = 0

        for p in base_path.rglob(file_pattern):
            if p.is_file() and not _should_ignore(p):
                files_searched += 1
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    lines = content.splitlines()
                    file_matches = []
                    
                    for i, line in enumerate(lines):
                        if literal:
                            if pattern in line:
                                file_matches.append((i + 1, line.strip()))
                        else:
                            if compiled_pattern.search(line):
                                file_matches.append((i + 1, line.strip()))
                                
                    if file_matches:
                        matches_found += len(file_matches)
                        output.append(f"--- {p} ---")
                        for line_num, matched_line in file_matches:
                            output.append(f"{line_num}: {matched_line}")
                        output.append("")
                except Exception:
                    pass

        if not output:
            return f"No matches found for '{pattern}' in {files_searched} files."
            
        output.insert(0, f"Found {matches_found} matches in {files_searched} files:\n")
        return "\n".join(output)
    return search_in_files

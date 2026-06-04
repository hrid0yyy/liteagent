import re
from pathlib import Path
from typing import List, Optional
import pathspec
from .providers import ToolProviderFactory

# Directories/names that are ALWAYS ignored, regardless of .gitignore or fallback
ALWAYS_IGNORE_NAMES = {".git", ".liteagent"}

# Fallback ignore patterns when no .gitignore exists (C# project focused)
FALLBACK_IGNORE_PATTERNS = [
    # Python
    "__pycache__",
    "*.pyc",
    ".venv",
    "*.egg-info",
    # Node
    "node_modules",
    # OS files
    ".DS_Store",
    "Thumbs.db",
    # IDE / Editor
    ".idea",
    ".vscode",
    "*.user",
    "*.suo",
    # C# / .NET build output
    "bin/",
    "obj/",
    ".vs/",
    "packages/",
    "TestResults/",
    # C# / .NET compiled & generated files
    "*.dll",
    "*.exe",
    "*.pdb",
    "*.cache",
    "*.log",
    # NuGet
    "*.nupkg",
    "nuget.exe",
    # Test & coverage
    ".pytest_cache",
    ".coverage",
    "htmlcov/",
    "coverage.xml",
    # Misc
    "*.min.js",
    "*.min.css",
    "*.map",
]


def _load_gitignore_spec(base_path: Path) -> Optional[pathspec.PathSpec]:
    """Load and parse .gitignore from the given base_path. Returns None if not found."""
    gitignore_path = base_path / ".gitignore"
    if gitignore_path.is_file():
        try:
            lines = gitignore_path.read_text(encoding="utf-8").splitlines()
            return pathspec.PathSpec.from_lines("gitwildmatch", lines)
        except Exception:
            return None
    return None


def _build_fallback_spec() -> pathspec.PathSpec:
    """Build a PathSpec from the fallback ignore patterns."""
    return pathspec.PathSpec.from_lines("gitwildmatch", FALLBACK_IGNORE_PATTERNS)


def create_search_in_files_tool(providers: ToolProviderFactory):
    def search_in_files(pattern: str, dir_path: str = ".", file_pattern: str = "*", literal: bool = False) -> str:
        """
        Searches for a string or regex pattern in files. Uses .gitignore if available, otherwise uses a fallback ignore list.
        
        Args:
            pattern: The search term or regex pattern to look for.
            dir_path: The directory to search in. Must be within the project directory. If outside or invalid, defaults to project directory. Defaults to current directory.
            file_pattern: Single glob pattern to filter files (e.g., '*.cs', '*.py', '*'). Only one pattern supported. Defaults to '*'.
            literal: If true, searches for the exact string. If false, treats pattern as regex. Defaults to false.
        """
        base_path = Path(dir_path).resolve()
        project_dir = providers.project_dir.resolve()

        # Validate dir_path: must exist and be within project directory
        dir_was_redirected = False
        if not base_path.exists() or not str(base_path).startswith(str(project_dir)):
            base_path = project_dir
            dir_was_redirected = True

        # Load ignore spec: try .gitignore first, then fallback
        spec = _load_gitignore_spec(base_path)
        using_gitignore = spec is not None
        if spec is None:
            spec = _build_fallback_spec()

        if not literal:
            try:
                compiled_pattern = re.compile(pattern)
            except re.error as e:
                return f"Error compiling regex: {e}"

        def _should_ignore(p: Path) -> bool:
            """Check if a path should be ignored based on the loaded spec."""
            # Always ignore certain names regardless of spec
            if p.name in ALWAYS_IGNORE_NAMES:
                return True
            try:
                rel_path = p.relative_to(base_path)
            except ValueError:
                return False
            rel_str = rel_path.as_posix()
            # Check both the file path and with trailing slash (for directory patterns)
            if spec.match_file(rel_str):
                return True
            # Also check if any parent directory is ignored
            for parent in rel_path.parents:
                parent_str = parent.as_posix()
                if parent_str and spec.match_file(parent_str + "/"):
                    return True
                if parent_str and spec.match_file(parent_str):
                    return True
            return False

        files_searched = 0
        matches_found = 0
        output = []

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

        ignore_source = ".gitignore" if using_gitignore else "fallback ignore list"
        result = f"Found {matches_found} matches in {files_searched} files (using {ignore_source}):\n"
        if dir_was_redirected:
            result += f"\n⚠ Directory redirected from '{dir_path}' to project directory '{base_path}'\n"
        output.insert(0, result)
        return "\n".join(output)
    return search_in_files

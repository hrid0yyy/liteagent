from pathlib import Path
from typing import Optional
import pathspec
from .providers import ToolProviderFactory

# Directories/names that are ALWAYS ignored, regardless of .gitignore or fallback
ALWAYS_IGNORE_NAMES = {".git", ".liteagent"}

# Fallback ignore patterns when no .gitignore exists (C# / .NET project focused)
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


def create_list_files_tool(providers: ToolProviderFactory):
    def list_files(pattern: str = "*", dir_path: str = ".") -> str:
        """
        Lists files matching a glob pattern. Uses .gitignore if available, otherwise uses a fallback ignore list.
        
        Args:
            pattern: Single glob pattern to filter files (e.g., '*.cs', '*.py', '*'). Only one pattern supported. Defaults to '*'.
            dir_path: The directory to list files from. Must be within the project directory. If outside or invalid, defaults to project directory. Defaults to current directory.
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

        def _should_ignore(p: Path) -> bool:
            """Check if a path should be ignored based on the loaded spec."""
            if p.name in ALWAYS_IGNORE_NAMES:
                return True
            try:
                rel_path = p.relative_to(base_path)
            except ValueError:
                return False
            rel_str = rel_path.as_posix()
            if spec.match_file(rel_str):
                return True
            # Also check if any parent directory is ignored
            for parent in rel_path.parents:
                parent_str = parent.as_posix()
                if parent_str and (spec.match_file(parent_str + "/") or spec.match_file(parent_str)):
                    return True
            return False

        output = []
        try:
            for p in base_path.rglob(pattern):
                if p.is_file() and not _should_ignore(p):
                    output.append(str(p.relative_to(base_path) if p.is_relative_to(base_path) else p))
        except Exception as e:
            return f"Error listing files: {str(e)}"

        if not output:
            return f"No files found matching '{pattern}' in {dir_path}"

        ignore_source = ".gitignore" if using_gitignore else "fallback ignore list"
        result = f"Found {len(output)} files (using {ignore_source}):\n"
        if dir_was_redirected:
            result += f"⚠ Directory redirected from '{dir_path}' to project directory '{base_path}'\n"
        return result + "\n".join(output)
    return list_files

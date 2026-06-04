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


def create_get_workspace_info_tool(providers: ToolProviderFactory):
    def get_workspace_info(dir_path: str = ".", max_depth: int = 3) -> str:
        """
        Lists the directory structure, respecting .gitignore or fallback ignore patterns, bounding depth.
        
        Args:
            dir_path: The directory to inspect. Must be within the project directory. If outside or invalid, defaults to project directory. Defaults to current directory.
            max_depth: Maximum depth of directory tree to display. Defaults to 3.
        """
        max_depth = int(max_depth) if max_depth not in (None, "") else 3
        output = []
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
            try:
                rel_path = p.relative_to(base_path)
            except ValueError:
                return False
            rel_str = rel_path.as_posix()
            # For directories, also check with trailing slash
            if p.is_dir():
                if spec.match_file(rel_str + "/") or spec.match_file(rel_str):
                    return True
            else:
                if spec.match_file(rel_str):
                    return True
            # Also check if any parent directory is ignored
            for parent in rel_path.parents:
                parent_str = parent.as_posix()
                if parent_str and (spec.match_file(parent_str + "/") or spec.match_file(parent_str)):
                    return True
            return False

        def _list_dir(current_path: Path, indent: str = ""):
            try:
                items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for i, item in enumerate(items):
                    if item.name in ALWAYS_IGNORE_NAMES or _should_ignore(item):
                        continue

                    is_last = i == len(items) - 1
                    connector = "└── " if is_last else "├── "
                    output.append(f"{indent}{connector}{item.name}{'/' if item.is_dir() else ''}")

                    if item.is_dir():
                        new_indent = indent + ("    " if is_last else "│   ")
                        if len(new_indent) // 4 < max_depth:
                            _list_dir(item, new_indent)
            except PermissionError:
                output.append(f"{indent} [Permission Denied]")

        ignore_source = ".gitignore" if using_gitignore else "fallback ignore list"
        output.append(f"Workspace: {base_path} (using {ignore_source})")
        if dir_was_redirected:
            output.append(f"⚠ Directory redirected from '{dir_path}' to project directory '{base_path}'")
        _list_dir(base_path)
        return "\n".join(output)
    return get_workspace_info

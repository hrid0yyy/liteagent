from pathlib import Path
from .providers import ToolProviderFactory

def create_rename_path_tool(providers: ToolProviderFactory):
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
            providers.container.read_tracker.rename_tracked_path(str(source), str(target))
            item_type = "directory" if target.is_dir() else "file"
            return f"Successfully renamed {item_type} from {old_path} to {new_path}"
        except Exception as e:
            return f"Error renaming {old_path} to {new_path}: {str(e)}"
    return rename_path

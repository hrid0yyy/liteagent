import shutil
from pathlib import Path
from .providers import ToolProviderFactory

def create_delete_path_tool(providers: ToolProviderFactory):
    def delete_path(path_to_delete: str) -> str:
        """Deletes a file or directory. Directories are removed recursively."""
        path = Path(path_to_delete)

        if not path.exists():
            return f"Error: Path {path_to_delete} does not exist."

        try:
            if path.is_file():
                path.unlink()
                providers.container.read_tracker.remove_tracked_path(str(path))
                return f"Successfully deleted file {path_to_delete}"
            if path.is_dir():
                shutil.rmtree(path)
                providers.container.read_tracker.remove_tracked_path(str(path))
                return f"Successfully deleted directory {path_to_delete}"
            return f"Error: Unsupported path type for {path_to_delete}"
        except Exception as e:
            return f"Error deleting {path_to_delete}: {str(e)}"
    return delete_path

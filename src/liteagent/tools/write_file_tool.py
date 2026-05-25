from pathlib import Path
from .providers import ToolProviderFactory

def create_write_file_tool(providers: ToolProviderFactory):
    def write_file(file_path: str, content: str) -> str:
        """Writes content to a file, overwriting if it exists."""
        path = Path(file_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing to {file_path}: {str(e)}"
    return write_file

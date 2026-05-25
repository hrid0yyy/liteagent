from pathlib import Path
from .providers import ToolProviderFactory

def create_list_files_tool(providers: ToolProviderFactory):
    def list_files(pattern: str = "*", dir_path: str = ".") -> str:
        """ Lists files matching a glob pattern (e.g., '**/*.py'). """
        base_path = Path(dir_path).resolve()
        if not base_path.exists():
            return f"Error: Directory {dir_path} does not exist."
            
        output = []
        try:
            for p in base_path.rglob(pattern):
                if p.is_file():
                    output.append(str(p.relative_to(base_path) if p.is_relative_to(base_path) else p))
        except Exception as e:
            return f"Error listing files: {str(e)}"
            
        if not output:
            return f"No files found matching '{pattern}' in {dir_path}"
            
        return "\n".join(output)
    return list_files

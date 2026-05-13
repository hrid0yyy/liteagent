from typing import Dict, Any, Callable, List, Optional, Union
import inspect

SAMPLE_INPUTS = {
    "get_workspace_info": {
        "dir_path": ".",
        "ignore_patterns": "['.git', '__pycache__']"
    },
    "search_in_files": {
        "pattern": "def.*",
        "dir_path": ".",
        "file_pattern": "**/*.py",
        "ignore_patterns": "['.venv', 'node_modules']",
        "literal": "false"
    },
    "list_files": {
        "pattern": "**/*.py",
        "dir_path": "."
    },
    "read_file": {
        "file_paths": "['src/main.py', 'README.md']",
        "start_line": "1",
        "end_line": "50"
    },
    "check_file_freshness": {
        "file_paths": "['src/main.py', 'README.md']"
    },
    "write_file": {
        "file_path": "new_file.txt",
        "content": "Hello, World!"
    },
    "rename_path": {
        "old_path": "old_name.txt",
        "new_path": "new_name.txt"
    },
    "delete_path": {
        "path_to_delete": "obsolete_folder"
    },
    "modify_file": {
        "edits": ">>> BEGIN\n>>> FILE : example.py\n>>> SEARCH\nold code\n+++ REPLACE\nnew code\n>>> END"
    },
    "run_shell_command": {
        "command": "dir",
        "timeout": "60"
    }
}

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: List[Dict[str, Any]] = []

    def register(self, func: Callable):
        name = func.__name__
        self.tools[name] = func
        
        sig = inspect.signature(func)
        params = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            param_info = {}
            
            # More robust type mapping
            if param.annotation == int:
                param_info["type"] = "integer"
            elif param.annotation == bool:
                param_info["type"] = "boolean"
            elif param.annotation == List[str] or param.annotation == Optional[List[str]]:
                param_info["type"] = "array"
                param_info["items"] = {"type": "string"}
            elif param.annotation == Union[str, type(None)] or param.annotation == Optional[str]:
                param_info["type"] = "string"
            elif param.annotation != inspect.Parameter.empty and hasattr(param.annotation, '__origin__'):
                # Handle generic types like Optional[List[str]]
                if hasattr(param.annotation, '__args__'):
                    arg = param.annotation.__args__[0]
                    if arg == list or arg == List:
                        param_info["type"] = "array"
                        param_info["items"] = {"type": "string"}
                    else:
                        param_info["type"] = "string"
                else:
                    param_info["type"] = "string"
            else:
                param_info["type"] = "string"
            
            param_info["description"] = f"Parameter: {param_name}"
            
            # Add sample input
            if name in SAMPLE_INPUTS and param_name in SAMPLE_INPUTS[name]:
                param_info["sample"] = SAMPLE_INPUTS[name][param_name]
            elif param.default is not inspect.Parameter.empty and param.default is not None:
                param_info["sample"] = repr(param.default)
            
            params["properties"][param_name] = param_info
            if param.default is inspect.Parameter.empty:
                params["required"].append(param_name)

        self.schemas.append({
            "name": name,
            "description": func.__doc__.strip() if func.__doc__ else "",
            "parameters": params
        })
        return func

registry = ToolRegistry()

# Registering tools
from .workspace import get_workspace_info, search_in_files, list_files
from .file_ops import read_file, check_file_freshness, write_file, rename_path, delete_path, modify_file
from .shell import run_shell_command

registry.register(get_workspace_info)
registry.register(search_in_files)
registry.register(list_files)
registry.register(read_file)
registry.register(check_file_freshness)
registry.register(write_file)
registry.register(rename_path)
registry.register(delete_path)
registry.register(modify_file)
registry.register(run_shell_command)

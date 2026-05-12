from typing import Dict, Any, Callable, List, Optional
import inspect

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
            else:
                param_info["type"] = "string"
            
            # Basic description from param name if docstring parsing isn't here yet
            param_info["description"] = f"Parameter: {param_name}"
            
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
from .workspace import get_workspace_info, search_in_files
from .file_ops import read_file, write_file, modify_file
from .shell import run_shell_command

registry.register(get_workspace_info)
registry.register(search_in_files)
registry.register(read_file)
registry.register(write_file)
registry.register(modify_file)
registry.register(run_shell_command)

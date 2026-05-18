from typing import Dict, Any, Callable, List, Optional, Union
import inspect
import time
from ..core.config import settings

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
        "file_path": "example.py",
        "edits": ">>> SEARCH\nold code\n+++ REPLACE\nnew code"
    },
    "run_shell_command": {
        "command": "dir",
        "timeout": "60"
    }
}

def _wrap_tool(func: Callable, tool_name: str, get_schema_fn: Callable) -> Callable:
    tool_allowed = ("*" in settings.summarize_tools) or (tool_name in settings.summarize_tools)
    
    async def summarizing_wrapper(**kwargs):
        will_summarize = kwargs.pop("will_summarize", True)
        
        start_time = time.time()
        if inspect.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)
            
        result_str = str(result)
        
        needs_compression = (
            settings.summarizer_enabled and 
            will_summarize and 
            tool_allowed and 
            len(result_str) > settings.summarizer_threshold
        )
        
        if needs_compression:
            from ..core.summarizer import summarize_payload
            from ..core.logger import log_event
            log_event("summarizer_triggered", "registry", {
                "tool": tool_name,
                "raw_size": len(result_str),
                "threshold": settings.summarizer_threshold
            })
            
            schema = get_schema_fn()
            tool_desc = schema.get("description", "") if schema else ""
            
            summary = await summarize_payload(tool_name, tool_desc, result_str)
            
            log_event("summarizer_completed", "registry", {
                "tool": tool_name,
                "summarized_size": len(summary),
                "duration_seconds": time.time() - start_time
            })
            
            return f"[NOTE: Raw payload was {len(result_str)} chars and was auto-summarized]\n\n{summary}"
            
        elif not will_summarize and len(result_str) > settings.summarizer_threshold:
            from ..core.logger import log_event
            log_event("summarizer_bypassed", "registry", {
                "tool": tool_name,
                "raw_size": len(result_str)
            })
            
        return result_str
        
    try:
        sig = inspect.signature(func)
        if settings.summarizer_enabled and tool_allowed:
            params = list(sig.parameters.values())
            if not any(p.name == "will_summarize" for p in params):
                params.append(inspect.Parameter(
                    "will_summarize", 
                    inspect.Parameter.KEYWORD_ONLY, 
                    default=True, 
                    annotation=bool
                ))
            summarizing_wrapper.__signature__ = sig.replace(parameters=params)
        else:
            summarizing_wrapper.__signature__ = sig
    except ValueError:
        pass
        
    summarizing_wrapper.__name__ = getattr(func, '__name__', 'wrapper')
    summarizing_wrapper.__doc__ = getattr(func, '__doc__', None)
    
    return summarizing_wrapper

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: List[Dict[str, Any]] = []

    def register_external_tool(self, name: str, schema: Dict[str, Any], func: Callable):
        """Registers a tool with a pre-defined schema (e.g., from MCP)."""
        tool_allowed = ("*" in settings.summarize_tools) or (name in settings.summarize_tools)
        if settings.summarizer_enabled and tool_allowed:
            if "parameters" in schema and "properties" in schema["parameters"]:
                if "will_summarize" not in schema["parameters"]["properties"]:
                    schema["parameters"]["properties"]["will_summarize"] = {
                        "type": "boolean",
                        "description": "Set to false to bypass the auto-summarizer and get the full raw output. Defaults to true to save context tokens.",
                        "default": True
                    }
                    from ..core.logger import log_event
                    log_event("summarizer_schema_injected", "registry", {"tool": name})
        
        def get_schema():
            return next((s for s in self.schemas if s["name"] == name), schema)
            
        wrapped_func = _wrap_tool(func, name, get_schema)
        self.tools[name] = wrapped_func
        # Ensure the schema has the correct name if it was modified
        schema["name"] = name
        self.schemas.append(schema)

    def register(self, func: Callable):
        name = func.__name__
        
        sig = inspect.signature(func)
        params = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            if param_name == "on_output":
                continue
                
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

        tool_allowed = ("*" in settings.summarize_tools) or (name in settings.summarize_tools)
        if settings.summarizer_enabled and tool_allowed:
            params["properties"]["will_summarize"] = {
                "type": "boolean",
                "description": "Set to false to bypass the auto-summarizer and get the full raw output. Defaults to true to save context tokens.",
                "default": True
            }
            from ..core.logger import log_event
            log_event("summarizer_schema_injected", "registry", {"tool": name})

        schema = {
            "name": name,
            "description": func.__doc__.strip() if func.__doc__ else "",
            "parameters": params
        }
        
        def get_schema():
            return schema
            
        wrapped_func = _wrap_tool(func, name, get_schema)
        self.tools[name] = wrapped_func
        
        self.schemas.append(schema)
        return func

registry = ToolRegistry()

# Registering tools
from .workspace import get_workspace_info, search_in_files, list_files
from .file_ops import read_file, write_file, rename_path, delete_path, modify_file
from .shell import run_shell_command

registry.register(get_workspace_info)
registry.register(search_in_files)
registry.register(list_files)
registry.register(read_file)
registry.register(write_file)
registry.register(rename_path)
registry.register(delete_path)
registry.register(modify_file)
registry.register(run_shell_command)

from typing import Dict, Any, List
import json
import inspect
import difflib
from pathlib import Path
from rich.prompt import Prompt
from rich.pretty import Pretty
from ...core.state import AgentState, app_state
from ...core.read_tracker import record_agent_write
from ...tools.registry import registry
from ...cli.formatter import console

def _extract_paths_for_diff(tool_name: str, args: Dict[str, Any]) -> List[str]:
    if tool_name == "write_file":
        file_path = args.get("file_path")
        return [file_path] if isinstance(file_path, str) and file_path.strip() else []

    if tool_name == "modify_file":
        edits = args.get("edits", "")
        if not isinstance(edits, str):
            return []
        paths = []
        for block in edits.split(">>> FILE : ")[1:]:
            lines = block.splitlines()
            if not lines:
                continue
            file_path = lines[0].strip()
            if file_path:
                paths.append(file_path)
        return list(dict.fromkeys(paths))

    return []

def _read_text_if_exists(file_path: str):
    path = Path(file_path)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None

def _build_unified_diff(file_path: str, before, after):
    before_lines = [] if before is None else before.splitlines()
    after_lines = [] if after is None else after.splitlines()
    diff_lines = list(difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm=""
    ))
    if not diff_lines:
        return None
    return "\n".join(diff_lines)


def _tool_succeeded(name: str, result: Any) -> bool:
    text = str(result)
    if name == "write_file":
        return text.startswith("Successfully wrote to ")
    if name == "modify_file":
        return ("Error" not in text) and ("Successfully applied" in text)
    return True

async def executor_node(state: AgentState) -> Dict[str, Any]:
    """Executes tool calls found in the messages with type conversion and optional user confirmation."""
    last_message = state["messages"][-1]
    tool_calls = last_message.get("tool_calls", [])
    
    outputs = []
    errors = []
    
    for call in tool_calls:
        function_info = call.get("function", call)
        name = function_info["name"]
        args = function_info.get("arguments", {})
        
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                errors.append(f"Failed to parse arguments for {name}: {args}")
                continue

        if name in registry.tools:
            try:
                func = registry.tools[name]
                sig = inspect.signature(func)
                
                # Perform automatic type conversion...
                typed_args = {}
                for param_name, param in sig.parameters.items():
                    if param_name in args:
                        val = args[param_name]
                        origin = getattr(param.annotation, "__origin__", None)
                        args_list = getattr(param.annotation, "__args__", [])
                        expected_types = [param.annotation]
                        if origin is not None:
                            expected_types = list(args_list)

                        try:
                            if int in expected_types and not isinstance(val, int):
                                typed_args[param_name] = int(val)
                            elif bool in expected_types and not isinstance(val, bool):
                                if isinstance(val, str):
                                    typed_args[param_name] = val.lower() == "true"
                                else:
                                    typed_args[param_name] = bool(val)
                            else:
                                typed_args[param_name] = val
                        except (ValueError, TypeError):
                            typed_args[param_name] = val
                    elif param.default is not inspect.Parameter.empty:
                        pass

                # Specific fix for get_workspace_info pattern list
                if name == "get_workspace_info" and "ignore_patterns" in typed_args:
                    val = typed_args["ignore_patterns"]
                    if isinstance(val, str):
                        typed_args["ignore_patterns"] = [p.strip() for p in val.replace("[", "").replace("]", "").replace("\"", "").split(",")]

                # Manual Confirmation Logic
                if not app_state.auto_mode:
                    allowed = False
                    while True:
                        console.print(f"\n[bold yellow]Permission Required:[/bold yellow] Agent wants to run [bold cyan]{name}[/bold cyan]")
                        choice = Prompt.ask("Allow execution?", choices=["y", "n", "v"], default="n")
                        
                        if choice == "y":
                            allowed = True
                            break
                        elif choice == "n":
                            allowed = False
                            break
                        elif choice == "v":
                            console.print("\n[bold]Parameters:[/bold]")
                            console.print(Pretty(typed_args))
                            # Loop back to ask again
                    
                    if not allowed:
                        outputs.append({
                            "tool_call_id": call.get("id"), 
                            "name": name,
                            "output": f"Error: User denied permission to execute tool '{name}'."
                        })
                        continue

                touched_paths = _extract_paths_for_diff(name, typed_args)
                before_contents = {path: _read_text_if_exists(path) for path in touched_paths}
                result = func(**typed_args)
                diffs = []
                after_contents = {}
                for path in touched_paths:
                    after_content = _read_text_if_exists(path)
                    after_contents[path] = after_content
                    before_content = before_contents.get(path)
                    if before_content != after_content and after_content is not None:
                        diff_text = _build_unified_diff(path, before_content, after_content)
                        if diff_text:
                            diffs.append({"path": path, "diff": diff_text})

                if name in {"write_file", "modify_file"} and _tool_succeeded(name, result):
                    for path in touched_paths:
                        after_content = after_contents.get(path)
                        if after_content is None:
                            continue
                        record_agent_write(path, after_content, operation_id=str(call.get("id", "")))

                outputs.append({
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "output": result,
                    "diffs": diffs
                })
            except Exception as e:
                import traceback
                errors.append(f"Error executing {name}: {str(e)}\n{traceback.format_exc()}")
        else:
            errors.append(f"Tool {name} not found.")

    tool_messages = [
        {"role": "tool", "content": str(out["output"]), "tool_call_id": out.get("tool_call_id")}
        for out in outputs
    ]
    
    return {
        "messages": tool_messages,
        "tool_outputs": outputs,
        "errors": errors
    }

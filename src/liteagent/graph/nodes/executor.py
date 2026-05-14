from typing import Dict, Any, List
import json
import inspect
import difflib
from pathlib import Path
from rich.prompt import Prompt
from rich.pretty import Pretty
from ...core.state import AgentState, app_state
from ...core.logger import log_event, log_error
from ...core.container import get_container
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


def _tool_error_payload(
    *,
    tool_name: str,
    tool_call_id: str,
    error_type: str,
    message: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "ok": False,
        "error_type": error_type,
        "message": message,
        "details": details,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
    }


def _append_tool_error(
    outputs: List[Dict[str, Any]],
    errors: List[str],
    *,
    tool_name: str,
    tool_call_id: str,
    error_type: str,
    message: str,
    details: Dict[str, Any],
) -> None:
    payload = _tool_error_payload(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        error_type=error_type,
        message=message,
        details=details,
    )
    outputs.append({
        "tool_call_id": tool_call_id,
        "name": tool_name,
        "output": json.dumps(payload, ensure_ascii=False),
        "diffs": [],
    })
    errors.append(f"{error_type} in {tool_name}: {message}")


def _validate_and_coerce_args(sig: inspect.Signature, args: Dict[str, Any]) -> (Dict[str, Any], List[Dict[str, Any]]):
    typed_args: Dict[str, Any] = {}
    validation_errors: List[Dict[str, Any]] = []

    if not isinstance(args, dict):
        return typed_args, [{
            "kind": "invalid_arguments_shape",
            "message": "Tool arguments must be a JSON object.",
            "received_type": type(args).__name__,
        }]

    unknown_args = [k for k in args.keys() if k not in sig.parameters]
    if unknown_args:
        validation_errors.append({
            "kind": "unknown_parameters",
            "parameters": unknown_args,
        })

    for param_name, param in sig.parameters.items():
        if param_name not in args:
            if param.default is inspect.Parameter.empty:
                validation_errors.append({
                    "kind": "missing_parameter",
                    "parameter": param_name,
                })
            continue

        value = args[param_name]
        origin = getattr(param.annotation, "__origin__", None)
        args_list = getattr(param.annotation, "__args__", [])
        expected_types = [param.annotation]
        if origin is not None:
            expected_types = list(args_list)

        if int in expected_types:
            if isinstance(value, int) and not isinstance(value, bool):
                typed_args[param_name] = value
            else:
                try:
                    typed_args[param_name] = int(value)
                except (ValueError, TypeError):
                    validation_errors.append({
                        "kind": "invalid_type",
                        "parameter": param_name,
                        "expected": "integer",
                        "received": type(value).__name__,
                        "value": value,
                    })
        elif bool in expected_types:
            if isinstance(value, bool):
                typed_args[param_name] = value
            elif isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "false"}:
                    typed_args[param_name] = lowered == "true"
                else:
                    validation_errors.append({
                        "kind": "invalid_type",
                        "parameter": param_name,
                        "expected": "boolean (true/false)",
                        "received": type(value).__name__,
                        "value": value,
                    })
            elif isinstance(value, int):
                if value in (0, 1):
                    typed_args[param_name] = bool(value)
                else:
                    validation_errors.append({
                        "kind": "invalid_type",
                        "parameter": param_name,
                        "expected": "boolean (0 or 1)",
                        "received": "int",
                        "value": value,
                    })
            else:
                validation_errors.append({
                    "kind": "invalid_type",
                    "parameter": param_name,
                    "expected": "boolean",
                    "received": type(value).__name__,
                    "value": value,
                })
        else:
            typed_args[param_name] = value

    return typed_args, validation_errors

async def executor_node(state: AgentState) -> Dict[str, Any]:
    """Executes tool calls found in the messages with type conversion and optional user confirmation."""
    last_message = state["messages"][-1]
    tool_calls = last_message.get("tool_calls", [])
    log_event("executor_start", "executor", {"tool_calls": tool_calls}, turn_index=app_state.turn_index)
    
    outputs = []
    errors = []
    
    for call in tool_calls:
        function_info = call.get("function", call)
        name = function_info.get("name", "unknown_tool")
        tool_call_id = call.get("id", "")
        args = function_info.get("arguments", {})
        log_event("tool_call_received", "executor", {"name": name, "raw_arguments": args, "call": call}, turn_index=app_state.turn_index)
        
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                _append_tool_error(
                    outputs,
                    errors,
                    tool_name=name,
                    tool_call_id=tool_call_id,
                    error_type="ARG_PARSE_ERROR",
                    message="Failed to parse tool arguments as JSON.",
                    details={"raw_arguments": function_info.get("arguments", {})},
                )
                log_event(
                    "tool_arg_parse_failed",
                    "executor",
                    {"name": name, "raw_arguments": function_info.get("arguments", {})},
                    level="error",
                    turn_index=app_state.turn_index,
                )
                continue
        elif not isinstance(args, dict):
            _append_tool_error(
                outputs,
                errors,
                tool_name=name,
                tool_call_id=tool_call_id,
                error_type="ARG_PARSE_ERROR",
                message="Tool arguments must be an object.",
                details={"received_type": type(args).__name__, "raw_arguments": args},
            )
            continue

        if name not in registry.tools:
            _append_tool_error(
                outputs,
                errors,
                tool_name=name,
                tool_call_id=tool_call_id,
                error_type="UNKNOWN_TOOL",
                message=f"Tool '{name}' not found.",
                details={"available_tools": sorted(list(registry.tools.keys()))},
            )
            log_event("tool_not_found", "executor", {"name": name}, level="error", turn_index=app_state.turn_index)
            continue

        func = registry.tools[name]
        sig = inspect.signature(func)
        typed_args, validation_errors = _validate_and_coerce_args(sig, args)

        # Specific fix for get_workspace_info pattern list
        if name == "get_workspace_info" and "ignore_patterns" in typed_args:
            val = typed_args["ignore_patterns"]
            if isinstance(val, str):
                typed_args["ignore_patterns"] = [p.strip() for p in val.replace("[", "").replace("]", "").replace("\"", "").split(",")]

        if validation_errors:
            _append_tool_error(
                outputs,
                errors,
                tool_name=name,
                tool_call_id=tool_call_id,
                error_type="VALIDATION_ERROR",
                message="Tool argument validation failed.",
                details={"validation_errors": validation_errors, "provided_args": args},
            )
            log_event(
                "tool_validation_failed",
                "executor",
                {"name": name, "validation_errors": validation_errors, "provided_args": args},
                level="error",
                turn_index=app_state.turn_index,
            )
            continue

        log_event("tool_args_typed", "executor", {"name": name, "typed_args": typed_args}, turn_index=app_state.turn_index)

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
            
            if not allowed:
                _append_tool_error(
                    outputs,
                    errors,
                    tool_name=name,
                    tool_call_id=tool_call_id,
                    error_type="PERMISSION_DENIED",
                    message=f"User denied permission to execute tool '{name}'.",
                    details={"typed_args": typed_args},
                )
                log_event("tool_permission_denied", "executor", {"name": name, "typed_args": typed_args}, level="warn", turn_index=app_state.turn_index)
                continue

        try:
            touched_paths = _extract_paths_for_diff(name, typed_args)
            before_contents = {path: _read_text_if_exists(path) for path in touched_paths}
            log_event("tool_execute_start", "executor", {"name": name, "typed_args": typed_args, "touched_paths": touched_paths}, turn_index=app_state.turn_index)
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
                    get_container().read_tracker.record_agent_write(path, after_content, operation_id=str(tool_call_id))
            log_event("tool_execute_end", "executor", {"name": name, "result": result, "diffs": diffs}, turn_index=app_state.turn_index)

            outputs.append({
                "tool_call_id": tool_call_id,
                "name": name,
                "output": result,
                "diffs": diffs
            })
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            _append_tool_error(
                outputs,
                errors,
                tool_name=name,
                tool_call_id=tool_call_id,
                error_type="RUNTIME_ERROR",
                message=f"Tool '{name}' execution failed: {str(e)}",
                details={"exception_type": type(e).__name__, "traceback": tb},
            )
            log_error(
                "executor",
                e,
                {"name": name, "traceback": tb},
                turn_index=app_state.turn_index,
            )

    tool_messages = [
        {"role": "tool", "content": str(out["output"]), "tool_call_id": out.get("tool_call_id")}
        for out in outputs
    ]
    
    result_state = {
        "messages": tool_messages,
        "tool_outputs": outputs,
        "errors": errors
    }
    log_event("executor_end", "executor", {"outputs": outputs, "errors": errors}, turn_index=app_state.turn_index)
    return result_state

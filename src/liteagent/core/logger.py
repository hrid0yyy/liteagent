import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, Optional

from .config import settings

_LOCK = threading.Lock()
_SESSION_ID = ""
_LOG_PATH = ""
_ENABLED = False
_NOISY_EVENTS = {"graph_event", "node_state", "assistant_message"}
_FULL_PAYLOAD_EVENTS = {
    "tool_call_received",
    "tool_args_typed",
    "tool_execute_start",
    "tool_execute_end",
    "server_tool_execute_request",
    "server_tool_execute_response",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars]"


def _truncate_structure(value: Any, max_chars: int) -> Any:
    if isinstance(value, str):
        return _truncate_text(value, max_chars)
    if isinstance(value, dict):
        return {k: _truncate_structure(v, max_chars) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_structure(v, max_chars) for v in value]
    return value


def _summarize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        summary = {}
        for key, value in payload.items():
            if key in {"messages", "tool_schemas", "response_json", "event", "state", "node_state"}:
                if isinstance(value, list):
                    summary[key] = f"<list len={len(value)}>"
                elif isinstance(value, dict):
                    summary[key] = f"<dict keys={len(value.keys())}>"
                else:
                    summary[key] = f"<{type(value).__name__}>"
            else:
                summary[key] = value
        return summary
    return payload


def _safe_payload(event_type: str, payload: Any) -> Any:
    try:
        # Always keep full payloads for tool I/O events.
        if event_type in _FULL_PAYLOAD_EVENTS:
            return payload

        # Collapse very noisy events to keep logs readable.
        if event_type in _NOISY_EVENTS:
            return _summarize_payload(payload)

        if settings.log_verbose_raw:
            serialized = json.dumps(payload, ensure_ascii=False, default=str)
            if len(serialized) <= settings.log_max_payload_chars:
                return payload
            return _truncate_structure(payload, 4000)

        return _truncate_structure(_summarize_payload(payload), 1000)
    except Exception as e:
        return f"payload_error={e}; payload_repr={repr(payload)[:2000]}"


def _record_to_text(record: Dict[str, Any]) -> str:
    event_type = record.get("event_type", "")
    payload = record.get("payload", {})
    level = record.get("level", "info")
    
    if not isinstance(payload, dict):
        if isinstance(payload, str):
            payload = {"raw_message": payload}
        else:
            try:
                payload = dict(payload)
            except (TypeError, ValueError):
                payload = {"raw_data": str(payload)}

    # Helper to collapse objects into a single line string
    def _to_single_line(obj: Any) -> str:
        if isinstance(obj, str):
            return obj.replace("\r", " ").replace("\n", " ").strip()
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            return str(obj).replace("\r", " ").replace("\n", " ").strip()

    # Capture ALL possible errors and warnings (including rate limits/retries)
    if level in ["error", "warn"] or "error" in event_type.lower() or "retry" in event_type.lower():
        tag = "[ERROR]" if level == "error" or "error" in event_type.lower() else "[WARNING]"
        error_msg = payload.get("error", payload.get("raw_message", _to_single_line(payload)))
        error_msg = _to_single_line(error_msg)
        component = record.get("component", "unknown")
        return f"{tag} ({event_type}) Component: {component} Payload: {error_msg}\n\n"
        
    if event_type == "session_started":
        settings_str = " ".join(f"{k}: {v}" for k, v in payload.items())
        return f"[CONFIG] Session Start: {record['ts']} {settings_str}\n\n"
        
    if event_type == "user_input":
        content = _to_single_line(payload.get("content", ""))
        return f"[USER PROMPT] {content}\n\n"
        
    if event_type == "tool_execute_start":
        name = payload.get("name", "")
        args_str = _to_single_line(payload.get("typed_args", {}))
        return f"[TOOL CALL] Tool: {name} Parameters: {args_str}\n\n"
        
    if event_type == "tool_execute_end":
        name = payload.get("name", "")
        result_str = _to_single_line(payload.get("result", ""))
        return f"[TOOL RESULT] Tool: {name} Output: {result_str}\n\n"
        
    if event_type == "assistant_message":
        msg = payload.get("message", {})
        
        # Skip tool messages that get passed here by mistake
        role = getattr(msg, "type", "") if hasattr(msg, "type") else msg.get("role", "") if isinstance(msg, dict) else ""
        if role == "tool":
            return ""
        
        if hasattr(msg, "content"):
            content = getattr(msg, "content", "")
            tool_calls = getattr(msg, "tool_calls", [])
            additional_kwargs = getattr(msg, "additional_kwargs", {})
            reasoning = additional_kwargs.get("reasoning_content", "") if isinstance(additional_kwargs, dict) else ""
            if hasattr(msg, "reasoning_content") and not reasoning:
                reasoning = getattr(msg, "reasoning_content", "")
        elif isinstance(msg, dict):
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            additional_kwargs = msg.get("additional_kwargs", {})
            reasoning = additional_kwargs.get("reasoning_content", "") if isinstance(additional_kwargs, dict) else ""
            if not reasoning:
                reasoning = msg.get("reasoning_content", "")
        else:
            content = str(msg)
            tool_calls = []
            reasoning = ""
            
        out = ""
        if reasoning:
            reasoning = _to_single_line(reasoning)
            out += f"[AGENT THINKING] {reasoning}\n\n"
            
        if content:
            content_str = _to_single_line(content)
            if not tool_calls and content_str.strip():
                out += f"[AGENT RESPONSE] {content_str}\n\n"
            elif content_str.strip():
                out += f"[AGENT THINKING] {content_str}\n\n"
                
        return out

    if event_type == "session_ended":
        summary = _to_single_line(payload)
        return f"[SESSION END] {summary}\n\n"

    # Suppress other verbose, internal events to declutter the log
    return ""


def _write_record(record: Dict[str, Any]) -> None:
    if not _ENABLED or not _LOG_PATH:
        return
    try:
        with _LOCK:
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(_record_to_text(record))
    except Exception:
        # Logging must never break runtime behavior.
        pass


def start_session_logger(session_id: str, mode: str, provider: str, model: str, cwd: str) -> str:
    global _SESSION_ID, _LOG_PATH, _ENABLED
    _ENABLED = bool(settings.log_enabled)
    if not _ENABLED:
        _SESSION_ID = session_id
        _LOG_PATH = ""
        return ""

    log_dir = Path(settings.log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    _SESSION_ID = session_id or str(uuid.uuid4())
    _LOG_PATH = str(log_dir / f"{_SESSION_ID}.log")

    log_event(
        event_type="session_started",
        component="cli",
        payload={
            "mode": mode,
            "provider": provider,
            "model": model,
            "cwd": cwd,
            "log_verbose_raw": settings.log_verbose_raw,
            "log_max_payload_chars": settings.log_max_payload_chars,
        },
    )
    return _LOG_PATH


def log_event(
    event_type: str,
    component: str,
    payload: Dict[str, Any],
    level: str = "info",
    turn_index: Optional[int] = None,
) -> None:
    record = {
        "ts": _utc_now(),
        "session_id": _SESSION_ID,
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "component": component,
        "level": level,
        "turn_index": turn_index,
        "payload": _safe_payload(event_type, payload),
    }
    _write_record(record)


def log_error(component: str, error: Any, payload: Optional[Dict[str, Any]] = None, turn_index: Optional[int] = None) -> None:
    data = {"error": str(error)}
    if payload:
        data.update(payload)
    log_event("error", component, data, level="error", turn_index=turn_index)


def end_session_logger(summary: Optional[Dict[str, Any]] = None) -> None:
    log_event("session_ended", "cli", payload=summary or {})


def get_session_log_path() -> str:
    return _LOG_PATH

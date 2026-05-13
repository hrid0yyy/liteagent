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
    header = (
        f"[{record['ts']}] {record['level'].upper()} "
        f"session={record['session_id']} turn={record.get('turn_index')} "
        f"component={record['component']} event={record['event_type']} id={record['event_id']}"
    )
    payload = record.get("payload")
    if isinstance(payload, str):
        payload_text = payload
    else:
        payload_text = pformat(payload, width=120, compact=False)
    return f"{header}\n{payload_text}\n{'-' * 100}\n"


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

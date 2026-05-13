import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List

from .state import app_state


def normalize_file_path(file_path: str) -> str:
    return os.path.normcase(str(Path(file_path).resolve()))


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _safe_stat(path: Path):
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def record_read(file_path: str, content: str, is_full_read: bool = True) -> None:
    normalized = normalize_file_path(file_path)
    path = Path(normalized)
    if not path.exists():
        return

    mtime_ns, size = _safe_stat(path)
    existing = app_state.read_tracker.get(normalized, {})
    app_state.read_tracker[normalized] = {
        "path": normalized,
        "last_read_at": time.time(),
        "last_known_mtime_ns": mtime_ns,
        "last_known_size": size,
        "last_known_hash": _hash_text(content) if is_full_read else None,
        "observed_version": int(existing.get("observed_version", 0)) + 1,
        "last_mutation_source": "external",
        "agent_has_fresh_knowledge": bool(is_full_read),
        "last_write_operation_id": existing.get("last_write_operation_id"),
    }


def record_agent_write(file_path: str, content: str, operation_id: str = "") -> None:
    normalized = normalize_file_path(file_path)
    path = Path(normalized)
    if not path.exists():
        return

    mtime_ns, size = _safe_stat(path)
    existing = app_state.read_tracker.get(normalized, {})
    app_state.read_tracker[normalized] = {
        "path": normalized,
        "last_read_at": float(existing.get("last_read_at", time.time())),
        "last_known_mtime_ns": mtime_ns,
        "last_known_size": size,
        "last_known_hash": _hash_text(content),
        "observed_version": int(existing.get("observed_version", 0)) + 1,
        "last_mutation_source": "agent",
        "agent_has_fresh_knowledge": True,
        "last_write_operation_id": operation_id or existing.get("last_write_operation_id"),
    }


def rename_tracked_path(old_path: str, new_path: str) -> None:
    old_normalized = normalize_file_path(old_path)
    new_normalized = normalize_file_path(new_path)
    updates: Dict[str, Dict[str, Any]] = {}
    removals: List[str] = []

    for tracked_path, entry in app_state.read_tracker.items():
        if tracked_path == old_normalized or tracked_path.startswith(old_normalized + os.sep):
            suffix = tracked_path[len(old_normalized):]
            mapped = new_normalized + suffix
            copied = dict(entry)
            copied["path"] = mapped
            updates[mapped] = copied
            removals.append(tracked_path)

    for key in removals:
        app_state.read_tracker.pop(key, None)
    app_state.read_tracker.update(updates)


def remove_tracked_path(path_to_remove: str) -> None:
    normalized = normalize_file_path(path_to_remove)
    removals = []
    for tracked_path in app_state.read_tracker.keys():
        if tracked_path == normalized or tracked_path.startswith(normalized + os.sep):
            removals.append(tracked_path)
    for key in removals:
        app_state.read_tracker.pop(key, None)


def check_file_freshness(file_paths: List[str]) -> str:
    """
    Checks whether files need to be re-read in this session.
    Returns per-file decisions as JSON.
    """
    decisions: List[Dict[str, Any]] = []

    for raw_path in file_paths:
        normalized = normalize_file_path(raw_path)
        path = Path(normalized)
        entry = app_state.read_tracker.get(normalized)

        if entry is None:
            decisions.append({
                "path": raw_path,
                "normalized_path": normalized,
                "should_read": True,
                "reason": "UNSEEN",
                "exists": path.exists(),
                "confidence": "low",
                "agent_has_fresh_knowledge": False,
                "hash_checked": False,
            })
            continue

        if not path.exists():
            decisions.append({
                "path": raw_path,
                "normalized_path": normalized,
                "should_read": True,
                "reason": "MISSING",
                "exists": False,
                "confidence": "low",
                "agent_has_fresh_knowledge": False,
                "hash_checked": False,
            })
            continue

        try:
            current_mtime_ns, current_size = _safe_stat(path)
        except Exception:
            decisions.append({
                "path": raw_path,
                "normalized_path": normalized,
                "should_read": True,
                "reason": "UNKNOWN",
                "exists": True,
                "confidence": "low",
                "agent_has_fresh_knowledge": bool(entry.get("agent_has_fresh_knowledge", False)),
                "hash_checked": False,
            })
            continue

        stored_mtime_ns = entry.get("last_known_mtime_ns")
        stored_size = entry.get("last_known_size")
        agent_has_knowledge = bool(entry.get("agent_has_fresh_knowledge", False))
        hash_checked = False

        if stored_mtime_ns == current_mtime_ns and stored_size == current_size:
            if agent_has_knowledge:
                decisions.append({
                    "path": raw_path,
                    "normalized_path": normalized,
                    "should_read": False,
                    "reason": "KNOWN_FRESH",
                    "exists": True,
                    "confidence": "high",
                    "agent_has_fresh_knowledge": True,
                    "hash_checked": False,
                    "last_known_mtime_ns": stored_mtime_ns,
                    "current_mtime_ns": current_mtime_ns,
                })
            else:
                decisions.append({
                    "path": raw_path,
                    "normalized_path": normalized,
                    "should_read": True,
                    "reason": "UNKNOWN",
                    "exists": True,
                    "confidence": "low",
                    "agent_has_fresh_knowledge": False,
                    "hash_checked": False,
                    "last_known_mtime_ns": stored_mtime_ns,
                    "current_mtime_ns": current_mtime_ns,
                })
            continue

        if entry.get("last_mutation_source") == "agent" and agent_has_knowledge and entry.get("last_known_hash"):
            try:
                current_hash = _hash_file(path)
                hash_checked = True
                if current_hash == entry.get("last_known_hash"):
                    app_state.read_tracker[normalized]["last_known_mtime_ns"] = current_mtime_ns
                    app_state.read_tracker[normalized]["last_known_size"] = current_size
                    decisions.append({
                        "path": raw_path,
                        "normalized_path": normalized,
                        "should_read": False,
                        "reason": "AGENT_MODIFIED",
                        "exists": True,
                        "confidence": "high",
                        "agent_has_fresh_knowledge": True,
                        "hash_checked": True,
                        "last_known_mtime_ns": stored_mtime_ns,
                        "current_mtime_ns": current_mtime_ns,
                    })
                    continue
            except Exception:
                pass

        app_state.read_tracker[normalized]["last_mutation_source"] = "external"
        app_state.read_tracker[normalized]["agent_has_fresh_knowledge"] = False
        decisions.append({
            "path": raw_path,
            "normalized_path": normalized,
            "should_read": True,
            "reason": "EXTERNALLY_MODIFIED",
            "exists": True,
            "confidence": "low",
            "agent_has_fresh_knowledge": False,
            "hash_checked": hash_checked,
            "last_known_mtime_ns": stored_mtime_ns,
            "current_mtime_ns": current_mtime_ns,
        })

    return json.dumps({"decisions": decisions}, indent=2)

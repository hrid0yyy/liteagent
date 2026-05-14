import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from .state import app_state


class ReadTracker:
    def __init__(self):
        self._lock = threading.RLock()
        self._store: Dict[str, Dict[str, Any]] = app_state.read_tracker

    def normalize_path(self, file_path: str) -> str:
        return os.path.normcase(str(Path(file_path).resolve()))

    def _hash_text(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _hash_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _safe_stat(self, path: Path):
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size

    def record_read(self, file_path: str, content: str, is_full_read: bool = True) -> None:
        normalized = self.normalize_path(file_path)
        path = Path(normalized)
        if not path.exists():
            return

        with self._lock:
            mtime_ns, size = self._safe_stat(path)
            existing = self._store.get(normalized, {})
            self._store[normalized] = {
                "path": normalized,
                "last_read_at": time.time(),
                "last_known_mtime_ns": mtime_ns,
                "last_known_size": size,
                "last_known_hash": self._hash_text(content) if is_full_read else None,
                "observed_version": int(existing.get("observed_version", 0)) + 1,
                "last_mutation_source": "external",
                "agent_has_fresh_knowledge": bool(is_full_read),
                "last_write_operation_id": existing.get("last_write_operation_id"),
            }

    def record_agent_write(self, file_path: str, content: str, operation_id: str = "") -> None:
        normalized = self.normalize_path(file_path)
        path = Path(normalized)
        if not path.exists():
            return

        with self._lock:
            mtime_ns, size = self._safe_stat(path)
            existing = self._store.get(normalized, {})
            self._store[normalized] = {
                "path": normalized,
                "last_read_at": float(existing.get("last_read_at", time.time())),
                "last_known_mtime_ns": mtime_ns,
                "last_known_size": size,
                "last_known_hash": self._hash_text(content),
                "observed_version": int(existing.get("observed_version", 0)) + 1,
                "last_mutation_source": "agent",
                "agent_has_fresh_knowledge": True,
                "last_write_operation_id": operation_id or existing.get("last_write_operation_id"),
            }

    def rename_tracked_path(self, old_path: str, new_path: str) -> None:
        old_normalized = self.normalize_path(old_path)
        new_normalized = self.normalize_path(new_path)
        updates: Dict[str, Dict[str, Any]] = {}
        removals: List[str] = []

        with self._lock:
            for tracked_path, entry in self._store.items():
                if tracked_path == old_normalized or tracked_path.startswith(old_normalized + os.sep):
                    suffix = tracked_path[len(old_normalized):]
                    mapped = new_normalized + suffix
                    copied = dict(entry)
                    copied["path"] = mapped
                    updates[mapped] = copied
                    removals.append(tracked_path)

            for key in removals:
                self._store.pop(key, None)
            self._store.update(updates)

    def remove_tracked_path(self, path_to_remove: str) -> None:
        normalized = self.normalize_path(path_to_remove)
        removals: List[str] = []

        with self._lock:
            for tracked_path in self._store.keys():
                if tracked_path == normalized or tracked_path.startswith(normalized + os.sep):
                    removals.append(tracked_path)
            for key in removals:
                self._store.pop(key, None)

    def check_freshness(self, file_paths: List[str]) -> Dict[str, Any]:
        decisions: List[Dict[str, Any]] = []

        with self._lock:
            for raw_path in file_paths:
                normalized = self.normalize_path(raw_path)
                path = Path(normalized)
                entry = self._store.get(normalized)

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
                    current_mtime_ns, current_size = self._safe_stat(path)
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
                        current_hash = self._hash_file(path)
                        hash_checked = True
                        if current_hash == entry.get("last_known_hash"):
                            self._store[normalized]["last_known_mtime_ns"] = current_mtime_ns
                            self._store[normalized]["last_known_size"] = current_size
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

                self._store[normalized]["last_mutation_source"] = "external"
                self._store[normalized]["agent_has_fresh_knowledge"] = False
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

        return {"decisions": decisions}

"""
Logbase Extraction Engine.

Scans the codebase (via the existing KnowledgeGraph) for methods containing
log statements.  Produces a hierarchical JSON file grouped by:

    Filepath → Class → Method → { log_lines, description, line_range }

Features:
  • Method-level hashing for incremental efficiency.
  • Optional LLM description generation (skip with empty=True).
  • Real-time progress callback for CLI/Inspector feedback.
"""
import hashlib
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..indexer.graph_store import KnowledgeGraph


# ── Types ────────────────────────────────────────────────────────────

ProgressCallback = Callable[[int, int, str], None]
"""(current, total, method_name) → None"""


# ── Helpers ──────────────────────────────────────────────────────────

def _method_hash(source_code: str) -> str:
    """Stable hash for a method's source code."""
    return hashlib.sha256(source_code.strip().encode("utf-8")).hexdigest()


def _regex_template_to_readable(template: str) -> str:
    """Convert a regex template back to readable format.
    e.g. '\\\\[APP\\\\] Command line args: (.*?)' → '[APP] Command line args: {...}'
    """
    import re
    result = template.replace('(.*?)', '{...}')
    result = re.sub(r'\\(.)', r'\1', result)
    return result


# ── Core ─────────────────────────────────────────────────────────────

class LogbaseExtractor:
    """Builds / incrementally updates `.liteagent/logbase.json`."""

    def __init__(self, project_dir: Path, graph_store: KnowledgeGraph):
        self._project_dir = project_dir
        self._graph_store = graph_store
        self._config_dir = project_dir / ".liteagent"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._logbase_path = self._config_dir / "logbase.json"
        self._hash_path = self._config_dir / "logbase_hashes.json"

    # ── Public API ───────────────────────────────────────────────────

    def extract(
        self,
        empty: bool = False,
        llm_describe: Optional[Callable[[str, str, str], str]] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Dict:
        """
        Run the extraction pipeline.

        Args:
            empty:        If True, skip LLM calls — description will be "".
            llm_describe: Callable(method_name, source_code, log_lines_str) → description.
                          Required when empty=False.
            on_progress:  Optional progress callback (current, total, method_name).

        Returns:
            The full logbase dict that was persisted.
        """
        # 1. Load existing caches
        prev_logbase = self._load_logbase()
        prev_hashes = self._load_hashes()

        # 2. Gather all methods that contain log statements from the KnowledgeGraph
        all_templates = self._graph_store.get_log_templates()
        if not all_templates:
            # No logs in codebase — write an empty logbase
            self._save_logbase({})
            self._save_hashes({})
            return {}

        # Group templates by file → method
        file_method_templates: Dict[str, Dict[str, List[str]]] = {}
        for t in all_templates:
            fp = t["file_path"]
            mn = t["method_name"]
            readable = _regex_template_to_readable(t["template"])
            file_method_templates.setdefault(fp, {}).setdefault(mn, []).append(readable)

        # 3. For each file/method, query its metadata from the graph
        methods_to_process: List[dict] = []
        for file_path, method_map in file_method_templates.items():
            method_rows = self._graph_store.get_methods_for_file(file_path)
            method_meta = {m["name"]: m for m in method_rows}
            for method_name, log_lines in method_map.items():
                meta = method_meta.get(method_name, {})
                source = self._get_method_source(file_path, meta)
                methods_to_process.append({
                    "file_path": file_path,
                    "class_name": meta.get("class_name") or "__module__",
                    "method_name": method_name,
                    "log_lines": log_lines,
                    "line_range": [meta.get("start_line", 0), meta.get("end_line", 0)],
                    "source_code": source,
                })

        # 4. Incremental processing
        new_hashes: Dict[str, str] = {}
        new_logbase: Dict = {}
        total = len(methods_to_process)

        for idx, item in enumerate(methods_to_process, 1):
            fp = item["file_path"]
            cls = item["class_name"]
            mn = item["method_name"]
            hash_key = f"{fp}::{cls}::{mn}"

            if on_progress:
                on_progress(idx, total, mn)

            current_hash = _method_hash(item["source_code"]) if item["source_code"] else ""
            new_hashes[hash_key] = current_hash

            # Check if unchanged → reuse cached description
            if current_hash and current_hash == prev_hashes.get(hash_key):
                cached_desc = self._get_cached_description(prev_logbase, fp, cls, mn)
                description = cached_desc if cached_desc is not None else ""
            elif empty or not llm_describe:
                description = ""
            else:
                log_lines_str = "\n".join(item["log_lines"])
                try:
                    description = llm_describe(mn, item["source_code"], log_lines_str)
                except Exception as e:
                    import traceback
                    print(f"[LogbaseExtractor] LLM describe failed for {mn}: {e}")
                    traceback.print_exc()
                    description = ""

            new_logbase.setdefault(fp, {}).setdefault(cls, {})[mn] = {
                "log_lines": item["log_lines"],
                "description": description,
                "line_range": item["line_range"],
            }

        # 5. Persist
        self._save_logbase(new_logbase)
        self._save_hashes(new_hashes)
        return new_logbase

    # ── Private helpers ──────────────────────────────────────────────

    def _get_method_source(self, file_path: str, meta: dict) -> str:
        """Read the method source from the file using line_range."""
        start = meta.get("start_line")
        end = meta.get("end_line")
        if not start or not end:
            return ""
        try:
            p = Path(file_path)
            if not p.exists():
                return ""
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            return "\n".join(lines[start - 1 : end])
        except Exception:
            return ""

    @staticmethod
    def _get_cached_description(logbase: dict, fp: str, cls: str, mn: str) -> Optional[str]:
        return logbase.get(fp, {}).get(cls, {}).get(mn, {}).get("description")

    # ── JSON I/O ─────────────────────────────────────────────────────

    def _load_logbase(self) -> Dict:
        if self._logbase_path.exists():
            try:
                return json.loads(self._logbase_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_logbase(self, data: Dict) -> None:
        self._logbase_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load_hashes(self) -> Dict[str, str]:
        if self._hash_path.exists():
            try:
                return json.loads(self._hash_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_hashes(self, data: Dict[str, str]) -> None:
        self._hash_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# ── LLM describer factory ───────────────────────────────────────────

def create_llm_describer(provider_name: str = None, model: str = None) -> Callable[[str, str, str], str]:
    """
    Create a synchronous `llm_describe(method_name, source_code, log_lines)` callable
    that uses the configured LLM provider to generate method descriptions.
    """
    import asyncio
    from ...core.config import settings
    from ...providers.factory import LLMProviderFactory

    provider_name = provider_name or settings.default_provider
    provider = LLMProviderFactory.create_provider(provider_name, model)

    def llm_describe(method_name: str, source_code: str, log_lines: str) -> str:
        prompt = (
            f"You are a senior software engineer. Given the following method source code and its log statements, "
            f"write a concise 1-2 sentence description of what this method does functionally. "
            f"Focus on business logic, not implementation details.\n\n"
            f"Method: {method_name}\n\n"
            f"Source code:\n```\n{source_code}\n```\n\n"
            f"Log statements found:\n{log_lines}\n\n"
            f"Description:"
        )
        messages = [{"role": "user", "content": prompt}]

        # Run the async generate in a sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an already-running event loop (e.g. FastAPI/CLI)
                # Use a new thread to avoid blocking
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(asyncio.run, provider.generate(messages)).result()
            else:
                result = loop.run_until_complete(provider.generate(messages))
        except RuntimeError:
            result = asyncio.run(provider.generate(messages))

        # Extract text from the provider response
        content = result.get("content", "")
        if isinstance(content, list):
            # Some providers return content as a list of parts
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        return content.strip()

    return llm_describe


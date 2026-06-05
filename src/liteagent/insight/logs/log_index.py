import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from ...core.config import settings


class LogIndex:
    """Log search with pre-search verification and 3-stage matching."""
    
    def __init__(self):
        self._known_log_messages: List[str] = []

    def set_known_log_messages(self, messages: List[str]) -> None:
        """Set known log message templates from extract_log_patterns tool."""
        self._known_log_messages = messages

    def _verify_query(self, query: str) -> bool:
        """Check if query could possibly match any known log pattern."""
        if not self._known_log_messages:
            return True  # No patterns extracted yet, allow all

        query_lower = query.lower()

        for template in self._known_log_messages:
            # Strip template params: "Processing order {OrderId}" → "Processing order "
            stripped = re.sub(r'\{[^}]+\}', '', template).strip().lower()

            # Exact substring match
            if stripped and stripped in query_lower:
                return True
            if query_lower in stripped:
                return True

            # Keyword overlap: any word from query appears in template
            query_words = set(query_lower.split())
            template_words = set(stripped.split())
            if query_words & template_words:
                return True

            # Partial word match: "app" is a substring of "appdomain"
            # Only check if query word is substring of template word (not reverse)
            for q_word in query_words:
                for t_word in template_words:
                    if len(q_word) >= 3 and q_word in t_word:
                        return True

        return False

    def _match_lines(self, lines: list, query: str, is_plain: bool) -> list:
        """
        Returns list of (line_index, is_fuzzy) tuples.
        Runs stages in order, stops as soon as a stage produces results.
        """
        query_lower = query.lower()

        # Stage 1 — case-insensitive exact match
        hits = [(i, False) for i, line in enumerate(lines) if query_lower in line.lower()]
        if hits:
            return hits

        # Stage 2 — regex (only when is_plain=False)
        if not is_plain:
            try:
                hits = [(i, False) for i, line in enumerate(lines)
                        if re.search(query, line, re.IGNORECASE)]
                if hits:
                    return hits
            except Exception:
                pass

        # Stage 3 — RapidFuzz partial_ratio
        try:
            from rapidfuzz import fuzz
            THRESHOLD = 70
            scored = []
            for i, line in enumerate(lines):
                score = fuzz.partial_ratio(query_lower, line.lower())
                if score >= THRESHOLD:
                    scored.append((score, i))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [(i, True) for _, i in scored]
        except ImportError:
            return []

    def search(self, query: str, is_plain: bool = True, context_lines: int = 2, last_hours: Optional[int] = None, limit: int = 1, force: bool = False) -> List[Dict[str, Any]]:
        """Search across all configured log files with pre-search verification."""
        # Pre-search verification (skip for regex queries)
        if is_plain and not force:
            if not self._verify_query(query):
                return [{"verification_blocked": True, "message": "No logging call in the codebase matches this query. The searched term cannot appear in log files. Use force=true to search anyway."}]

        results = []
        for path_str in settings.insight_log_paths:
            log_file = Path(path_str)
            if not log_file.exists():
                continue
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    total_lines = len(lines)

                    matched = self._match_lines(lines, query, is_plain)

                    # If it's stage 1/2, they are in forward order, but we want newest first
                    # If it's stage 3, they are in relevance order.
                    is_fuzzy = any(m[1] for m in matched)
                    if not is_fuzzy:
                        matched.sort(key=lambda x: x[0], reverse=True)

                    for i, fuzzy in matched:
                        line = lines[i]

                        start_idx = max(0, i - context_lines)
                        end_idx = min(total_lines, i + context_lines + 1)

                        line_context = []
                        for j in range(start_idx, end_idx):
                            prefix = ">> " if j == i else "   "
                            line_context.append(f"{prefix}{j + 1}: {lines[j].strip()}")

                        context_block = "\n".join(line_context)

                        results.append({
                            "line_number": i + 1,
                            "timestamp": line.split("]")[0][1:] if "]" in line else "",
                            "level": "ERROR" if "[ERROR]" in line else "INFO",
                            "file_path": str(log_file),
                            "message": line.strip(),
                            "context": context_block,
                            "fuzzy": fuzzy
                        })
                        if len(results) >= limit:
                            break
            except Exception:
                pass
            if len(results) >= limit:
                break
        return results

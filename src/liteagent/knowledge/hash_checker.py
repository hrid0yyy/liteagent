"""
Hash-based change detection for codebase.

This module provides simple hash-based change detection that works with:
- Git repositories (uses git write-tree)
- Non-git projects (hashes source files)
"""

import subprocess
import hashlib
from pathlib import Path
from typing import Optional


class HashChecker:
    """
    Simple hash-based change detection.
    
    Works with:
    - Git repositories (uses git write-tree)
    - Non-git projects (hashes source files)
    """
    
    # Comprehensive list of source code file extensions
    CODE_EXTENSIONS = {
        # Python
        ".py", ".pyw", ".pyi", ".pyx",
        # JavaScript/TypeScript
        ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
        # Java/JVM
        ".java", ".kt", ".kts", ".scala", ".groovy", ".gradle",
        # C/C++
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh", ".hxx",
        # C#
        ".cs",
        # Go
        ".go",
        # Rust
        ".rs",
        # Ruby
        ".rb", ".rake", ".gemspec",
        # PHP
        ".php", ".phtml", ".php3", ".php4", ".php5",
        # Swift/Objective-C
        ".swift", ".m", ".mm", ".h",
        # Web
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        # Shell/Scripts
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
        # Config/Data
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        # Markup
        ".md", ".rst", ".adoc",
        # Database
        ".sql", ".prisma",
        # Other
        ".lua", ".r", ".ex", ".exs", ".erl", ".hs", ".clj", ".lisp",
        ".vue", ".svelte", ".astro",
    }
    
    IGNORE_PATTERNS = [
        ".git", "__pycache__", "node_modules", 
        ".venv", "venv", "env", ".env",
        ".idea", ".vscode", ".sublime",
        "dist", "build", "target", "out", "bin", "obj",
        ".egg-info", ".pyc", ".pyo",
        "vendor", "Pods", ".gradle", ".mvn",
    ]
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.stored_hash: str = ""
    
    def get_current_hash(self) -> str:
        """
        Get current codebase hash.
        
        Prefers git tree hash (fast), falls back to file hashing.
        
        Returns:
            Hash string prefixed with 'git:' or 'files:'
        """
        # Try git first (fastest)
        git_hash = self._get_git_hash()
        if git_hash:
            return git_hash
        
        # Fallback: hash source files
        return self._hash_source_files()
    
    def _get_git_hash(self) -> Optional[str]:
        """Get git tree hash if in a git repository."""
        try:
            result = subprocess.run(
                ["git", "write-tree"],
                capture_output=True,
                text=True,
                cwd=str(self.project_path),
                timeout=5
            )
            if result.returncode == 0:
                return f"git:{result.stdout.strip()}"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        return None
    
    def _hash_source_files(self) -> str:
        """Hash all source files (slower but works everywhere)."""
        hasher = hashlib.sha256()
        
        # Get all code files
        code_files = []
        for ext in self.CODE_EXTENSIONS:
            code_files.extend(self.project_path.rglob(f"*{ext}"))
        
        # Sort for consistent ordering
        for file_path in sorted(code_files):
            # Skip ignore patterns
            if any(pattern in str(file_path) for pattern in self.IGNORE_PATTERNS):
                continue
            
            try:
                # Hash file path + content
                hasher.update(str(file_path.relative_to(self.project_path)).encode())
                hasher.update(file_path.read_bytes())
            except Exception:
                continue
        
        return f"files:{hasher.hexdigest()[:16]}"
    
    def has_changed(self) -> bool:
        """
        Check if codebase has changed since last check.
        
        Updates stored hash automatically.
        
        Returns:
            True if codebase has changed, False otherwise
        """
        current = self.get_current_hash()
        changed = current != self.stored_hash
        self.stored_hash = current
        return changed
    
    def get_stored_hash(self) -> str:
        """Get the stored hash without checking."""
        return self.stored_hash
    
    def update_stored_hash(self, hash_value: str = None):
        """
        Manually update stored hash.
        
        Args:
            hash_value: Hash to store, or None to use current hash
        """
        self.stored_hash = hash_value or self.get_current_hash()
    
    def force_changed(self):
        """Force the next check to report as changed by clearing stored hash."""
        self.stored_hash = ""

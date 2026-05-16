# Knowledge Base Integration Plan

## Overview

This document outlines the detailed plan for integrating the `code-review-graph` wiki output as a knowledge base for the LiteAgent. The knowledge base will provide the agent with deep understanding of the codebase structure, relationships, and architecture.

---

## Goals

1. **Session Initialization**: Build/load knowledge base when a session starts
2. **Context Injection**: Provide relevant knowledge to the agent's system prompt
3. **Auto-Update**: Keep knowledge base synchronized with codebase changes
4. **Context Management**: Replace old KB content to avoid context pollution

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LiteAgent Session                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    WikiKnowledgeManager                       │   │
│  │                                                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │   │
│  │  │   Builder   │  │   Loader    │  │   HashChecker       │   │   │
│  │  │             │  │             │  │                     │   │   │
│  │  │ - build()   │  │ - load()    │  │ - get_hash()        │   │   │
│  │  │ - update()  │  │ - get_ctx() │  │ - has_changed()     │   │   │
│  │  │ - status()  │  │ - refresh() │  │ - store_hash()      │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │   │
│  │                                                               │   │
│  └────────────────────────────┬─────────────────────────────────┘   │
│                               │                                      │
│                               ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │               KnowledgeBaseContextManager                     │   │
│  │                                                               │   │
│  │  - Inject KB with markers into system prompt                 │   │
│  │  - Replace old KB in message history when updated            │   │
│  │                                                               │   │
│  └────────────────────────────┬─────────────────────────────────┘   │
│                               │                                      │
│                               ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     System Prompt                             │   │
│  │                                                               │   │
│  │  <!-- KNOWLEDGE_BASE_START -->                               │   │
│  │  ... current KB content ...                                   │   │
│  │  <!-- KNOWLEDGE_BASE_END -->                                 │   │
│  │                                                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Hash-Based Change Detection (Simplified)

Instead of complex file watchers and tool hooks, we use a simple hash-based approach:

- **Before each agent turn**, calculate hash of codebase
- **Compare with stored hash** to detect changes
- **If changed**, update KB and refresh context

**Benefits**:
- Works for ALL change sources (tools, human edits, git, external editors)
- No file system watcher needed
- No tool wrapper hooks needed
- Simple and reliable

### 2. Message History Replacement

When KB is updated, we replace the old KB content in the message history:

- **Markers**: Wrap KB content with `<!-- KNOWLEDGE_BASE_START -->` and `<!-- KNOWLEDGE_BASE_END -->`
- **Replacement**: Find and replace marked content in all system messages
- **Result**: LLM only sees current KB, no context pollution

---

## File Structure

```
src/liteagent/
├── knowledge/
│   ├── __init__.py
│   ├── manager.py           # WikiKnowledgeManager class
│   ├── loader.py            # Wiki file loading utilities
│   ├── hash_checker.py      # Hash-based change detection
│   └── context_manager.py   # KB context management in messages
├── core/
│   ├── config.py            # Add CRG settings (MODIFY)
│   └── state.py             # Add knowledge_base field (MODIFY)
├── graph/nodes/
│   └── planner.py           # Inject knowledge context (MODIFY)
└── cli/
    └── main.py              # Initialize knowledge base (MODIFY)
```

---

## Implementation Details

### Phase 1: Configuration Settings

**File**: `src/liteagent/core/config.py`

Add the following settings:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Code Review Graph - Knowledge Base Settings
    crg_enabled: bool = False                    # Enable knowledge base feature
    crg_auto_build: bool = True                  # Build graph on session start if not exists
    crg_check_hash_before_turn: bool = True      # Check hash before each agent turn
    crg_update_async: bool = True                # Update without blocking agent
    crg_wiki_dir: str = ".code-review-graph/wiki"  # Wiki output directory
    crg_context_max_chars: int = 50000           # Max characters for KB context
    crg_include_sections: List[str] = [          # Which wiki sections to include
        "architecture",
        "communities", 
        "hubs",
        "bridges",
        "flows"
    ]
```

### Phase 2: State Management

**File**: `src/liteagent/core/state.py`

Add knowledge base tracking to AppState:

```python
class AppState:
    def __init__(self):
        # ... existing fields ...
        
        # Knowledge Base
        self.knowledge_base: str = ""
        self.knowledge_base_loaded: bool = False
        self.knowledge_base_hash: str = ""  # Hash of current KB content
        self.codebase_hash: str = ""        # Hash of codebase files
```

### Phase 3: Hash Checker

**File**: `src/liteagent/knowledge/hash_checker.py`

```python
"""
Hash-based change detection for codebase.
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
        "*.egg-info", "*.pyc", "*.pyo",
        "vendor", "Pods", ".gradle", ".mvn",
    ]
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.stored_hash: str = ""
    
    def get_current_hash(self) -> str:
        """
        Get current codebase hash.
        
        Prefers git tree hash (fast), falls back to file hashing.
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
        """
        current = self.get_current_hash()
        changed = current != self.stored_hash
        self.stored_hash = current
        return changed
    
    def get_stored_hash(self) -> str:
        """Get the stored hash without checking."""
        return self.stored_hash
    
    def update_stored_hash(self, hash_value: str = None):
        """Manually update stored hash."""
        self.stored_hash = hash_value or self.get_current_hash()
```

### Phase 4: Wiki Loader

**File**: `src/liteagent/knowledge/loader.py`

```python
"""
Wiki file loading utilities.
"""
from pathlib import Path
from typing import Dict, List, Optional


class WikiLoader:
    """Loads and parses wiki markdown files."""
    
    def __init__(self, wiki_dir: str):
        self.wiki_dir = Path(wiki_dir)
    
    def wiki_exists(self) -> bool:
        """Check if wiki directory exists and has content."""
        return self.wiki_dir.exists() and any(self.wiki_dir.glob("*.md"))
    
    def list_wiki_files(self) -> List[Path]:
        """List all markdown files in wiki directory."""
        return list(self.wiki_dir.glob("*.md"))
    
    def load_file(self, filename: str) -> Optional[str]:
        """Load a specific wiki file."""
        path = self.wiki_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    
    def load_all(self) -> Dict[str, str]:
        """Load all wiki files into a dictionary."""
        wiki_content = {}
        for file_path in self.list_wiki_files():
            wiki_content[file_path.name] = file_path.read_text(encoding="utf-8")
        return wiki_content
    
    def get_mtime(self) -> float:
        """Get the most recent modification time of wiki files."""
        mtimes = [f.stat().st_mtime for f in self.list_wiki_files()]
        return max(mtimes) if mtimes else 0
```

### Phase 5: Context Manager

**File**: `src/liteagent/knowledge/context_manager.py`

```python
"""
Knowledge base context management in message history.
"""
import re
from typing import List, Dict, Any


class KnowledgeBaseContextManager:
    """
    Manages KB content in message history.
    
    Uses markers to identify KB content, allowing replacement
    when the knowledge base is updated.
    """
    
    KB_START_MARKER = "<!-- KNOWLEDGE_BASE_START -->"
    KB_END_MARKER = "<!-- KNOWLEDGE_BASE_END -->"
    
    @classmethod
    def wrap_kb(cls, content: str) -> str:
        """
        Wrap KB content with markers for later replacement.
        
        Args:
            content: The knowledge base content
            
        Returns:
            Content wrapped with start/end markers
        """
        return f"""
{cls.KB_START_MARKER}
{content}
{cls.KB_END_MARKER}
"""
    
    @classmethod
    def update_messages(cls, messages: List[Dict[str, Any]], new_kb: str) -> List[Dict[str, Any]]:
        """
        Replace old KB with new KB in all messages.
        
        This ensures the LLM only sees the current knowledge base,
        preventing context pollution from outdated KB content.
        
        Args:
            messages: List of message dictionaries
            new_kb: New knowledge base content (will be wrapped with markers)
            
        Returns:
            Updated messages list with replaced KB content
        """
        pattern = f"{re.escape(cls.KB_START_MARKER)}.*?{re.escape(cls.KB_END_MARKER)}"
        replacement = cls.wrap_kb(new_kb)
        
        updated_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                # Replace KB in system messages
                new_content = re.sub(pattern, replacement, msg["content"], flags=re.DOTALL)
                updated_messages.append({**msg, "content": new_content})
            else:
                updated_messages.append(msg)
        
        return updated_messages
    
    @classmethod
    def has_kb_content(cls, content: str) -> bool:
        """Check if content contains KB markers."""
        return cls.KB_START_MARKER in content and cls.KB_END_MARKER in content
    
    @classmethod
    def extract_kb(cls, content: str) -> str:
        """Extract KB content from marked section."""
        pattern = f"{re.escape(cls.KB_START_MARKER)}(.*?){re.escape(cls.KB_END_MARKER)}"
        match = re.search(pattern, content, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
```

### Phase 6: Wiki Knowledge Manager

**File**: `src/liteagent/knowledge/manager.py`

```python
"""
Main knowledge base manager.
"""
import asyncio
from pathlib import Path
from typing import List, Optional
from .loader import WikiLoader
from .hash_checker import HashChecker
from .context_manager import KnowledgeBaseContextManager
from ..core.config import settings
from ..core.state import app_state
from ..core.logger import log_event, log_error


class WikiKnowledgeManager:
    """
    Manages code-review-graph wiki as agent knowledge base.
    
    Responsibilities:
    - Build/update the knowledge graph
    - Load wiki content
    - Build context for agent
    - Detect changes via hash
    """
    
    def __init__(
        self,
        project_path: str = ".",
        wiki_dir: str = None,
        max_context_chars: int = None
    ):
        self.project_path = Path(project_path).resolve()
        self.wiki_dir = wiki_dir or settings.crg_wiki_dir
        self.max_context_chars = max_context_chars or settings.crg_context_max_chars
        
        # Initialize components
        self.loader = WikiLoader(self.wiki_dir)
        self.hash_checker = HashChecker(str(self.project_path))
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize the knowledge base.
        
        Steps:
        1. Check if graph exists
        2. Build if needed
        3. Generate wiki if needed
        4. Load context
        5. Store initial hash
        
        Returns:
            True if initialization successful
        """
        try:
            # Step 1: Check graph status
            status = await self._run_crg_command("status")
            
            # Step 2: Build if needed
            if settings.crg_auto_build and ("not built" in status.lower() or "error" in status.lower()):
                log_event("knowledge_base_build_start", "manager", {})
                await self._run_crg_command("build", timeout=300)
                log_event("knowledge_base_build_end", "manager", {})
            
            # Step 3: Generate wiki if needed
            if not self.loader.wiki_exists():
                log_event("knowledge_base_wiki_start", "manager", {})
                await self._run_crg_command("wiki")
                log_event("knowledge_base_wiki_end", "manager", {})
            
            # Step 4: Load context
            await self.refresh_context()
            
            # Step 5: Store initial hash
            self.hash_checker.update_stored_hash()
            
            self._initialized = True
            log_event("knowledge_base_initialized", "manager", {
                "wiki_exists": self.loader.wiki_exists(),
                "context_length": len(app_state.knowledge_base)
            })
            
            return True
            
        except Exception as e:
            log_error("manager", e, {"phase": "initialize"})
            return False
    
    async def check_and_update(self) -> bool:
        """
        Check if codebase changed and update KB if needed.
        
        This should be called before each agent turn.
        
        Returns:
            True if KB was updated, False otherwise
        """
        if not self._initialized:
            return False
        
        if not self.hash_checker.has_changed():
            return False
        
        log_event("knowledge_base_change_detected", "manager", {
            "old_hash": self.hash_checker.get_stored_hash()
        })
        
        # Update the knowledge base
        return await self.update_graph()
    
    async def update_graph(self) -> bool:
        """
        Update the knowledge graph and wiki.
        
        Returns:
            True if update successful
        """
        try:
            # Incremental update (auto-detect from git)
            await self._run_crg_command("update", timeout=120)
            
            # Regenerate wiki
            await self._run_crg_command("wiki")
            
            # Refresh context
            await self.refresh_context()
            
            # Update stored hash
            self.hash_checker.update_stored_hash()
            
            log_event("knowledge_base_updated", "manager", {
                "new_hash": self.hash_checker.get_stored_hash()
            })
            
            return True
            
        except Exception as e:
            log_error("manager", e, {"phase": "update_graph"})
            return False
    
    async def refresh_context(self) -> str:
        """
        Refresh the knowledge base context.
        
        Returns:
            The updated context string
        """
        wiki_content = self.loader.load_all()
        
        if not wiki_content:
            app_state.knowledge_base = ""
            app_state.knowledge_base_loaded = False
            return ""
        
        # Build context with size limit
        context = self._build_context(wiki_content)
        
        app_state.knowledge_base = context
        app_state.knowledge_base_loaded = bool(context)
        
        log_event("knowledge_base_refreshed", "manager", {
            "context_length": len(context)
        })
        
        return context
    
    def _build_context(self, wiki_content: dict) -> str:
        """Build context string from wiki files."""
        # Priority order
        priority = ["architecture", "communities", "hubs", "bridges", "flows", "README"]
        
        # Sort files by priority
        sorted_files = []
        remaining = set(wiki_content.keys())
        
        for p in priority:
            for filename in list(remaining):
                if p.lower() in filename.lower():
                    sorted_files.append(filename)
                    remaining.remove(filename)
                    break
        
        # Add remaining files
        sorted_files.extend(sorted(remaining))
        
        # Build context with size limit
        parts = []
        current_size = 0
        
        for filename in sorted_files:
            content = wiki_content.get(filename, "")
            if not content:
                continue
            
            # Check size limit
            if current_size + len(content) > self.max_context_chars:
                remaining_space = self.max_context_chars - current_size
                if remaining_space > 500:
                    content = content[:remaining_space] + "\n\n... [truncated]"
                else:
                    break
            
            parts.append(f"### {filename}\n\n{content}")
            current_size += len(content)
        
        if not parts:
            return ""
        
        return self._format_context(parts)
    
    def _format_context(self, parts: List[str]) -> str:
        """Format context for system prompt."""
        return f"""
## CODEBASE KNOWLEDGE BASE

The following knowledge has been extracted from your codebase structure.
Use this to understand the project architecture, relationships, and key components.
You can also use crg_* tools to query specific information dynamically.

---

{chr(10).join(parts)}

---
"""
    
    def get_context(self) -> str:
        """Get the current knowledge base context."""
        return app_state.knowledge_base
    
    def is_initialized(self) -> bool:
        """Check if knowledge base is initialized."""
        return self._initialized
    
    async def _run_crg_command(self, args: str, timeout: int = 60) -> str:
        """
        Run a code-review-graph CLI command.
        
        Args:
            args: Command arguments (e.g., "build", "update", "wiki")
            timeout: Command timeout in seconds
            
        Returns:
            Command output
        """
        cmd = f"code-review-graph {args}"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_path)
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        if process.returncode != 0:
            error_msg = stderr.decode() or "Unknown error"
            raise RuntimeError(f"CRG command failed: {error_msg}")
        
        return stdout.decode()
```

### Phase 7: CLI Integration

**File**: `src/liteagent/cli/main.py` (modifications)

```python
# Add to imports
from ..knowledge.manager import WikiKnowledgeManager

# Add new CLI option
@app.command()
def chat(
    provider_name: str = typer.Option(settings.default_provider, "--provider", "-p"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    resume: Optional[str] = typer.Option(None, "--resume", "-r"),
    inspector: bool = typer.Option(False, "--inspector", "-i"),
    # NEW: Knowledge base option
    crg: bool = typer.Option(False, "--crg", help="Enable code-review-graph knowledge base"),
):
    """Open an interactive chat session with the agent."""
    try:
        asyncio.run(_run_chat(provider_name, model, resume, inspector, crg))
    except KeyboardInterrupt:
        pass

# Modify _run_chat function
async def _run_chat(
    provider_name: str, 
    model: Optional[str], 
    resume: Optional[str], 
    inspector: bool = True,
    crg: bool = False  # NEW parameter
):
    # ... existing initialization code ...
    
    # NEW: Initialize knowledge base if CRG enabled
    knowledge_manager = None
    if crg or settings.crg_enabled:
        knowledge_manager = WikiKnowledgeManager()
        initialized = await knowledge_manager.initialize()
        
        if initialized:
            console.print("[bold green]Knowledge base loaded successfully.[/bold green]")
        else:
            console.print("[bold yellow]Warning: Knowledge base initialization failed.[/bold yellow]")
    
    # ... rest of the function ...
```

### Phase 8: Planner Integration

**File**: `src/liteagent/graph/nodes/planner.py` (modifications)

```python
from ...core.state import app_state
from ...knowledge.manager import WikiKnowledgeManager
from ...knowledge.context_manager import KnowledgeBaseContextManager

# Global knowledge manager reference
_knowledge_manager: WikiKnowledgeManager = None

def set_knowledge_manager(manager: WikiKnowledgeManager):
    """Set the knowledge manager for the planner."""
    global _knowledge_manager
    _knowledge_manager = manager

async def planner_node(state: AgentState, provider: BaseProvider) -> Dict[str, Any]:
    """Core Agent Node (ReAct): Reasons about the task and decides on actions."""
    messages = state["messages"]
    cwd = os.getcwd()
    
    # Check for KB update before processing
    if _knowledge_manager and settings.crg_check_hash_before_turn:
        if await _knowledge_manager.check_and_update():
            # KB was updated - replace old KB in message history
            messages = KnowledgeBaseContextManager.update_messages(
                messages, 
                app_state.knowledge_base
            )
    
    # Build knowledge context
    knowledge_context = ""
    if app_state.knowledge_base_loaded and app_state.knowledge_base:
        knowledge_context = KnowledgeBaseContextManager.wrap_kb(app_state.knowledge_base)
    
    system_prompt = {
        "role": "system",
        "content": (
            f"You are a coding agent. Current directory: {cwd}\n\n"
            f"{knowledge_context}\n\n"
            "CRITICAL RULES (DO NOT IGNORE):\n"
            "1. SINGLE TOOL CALL: You MUST ONLY CALL ONE TOOL AT A TIME.\n"
            "2. ZERO HALLUCINATION: You MUST NOT guess or make up file names.\n"
            "3. READ BEFORE MODIFY: Always 'read_file' before 'modify_file'.\n"
            "4. KNOWLEDGE BASE: Use crg_* tools to query code relationships.\n"
            # ... other rules ...
        )
    }
    
    # ... rest of the function ...
```

---

## Update Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE BASE UPDATE FLOW                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Session Start (--crg)                                          │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 1. Check if graph exists (crg status)                   │   │
│  │ 2. Build if needed (crg build)                          │   │
│  │ 3. Generate wiki (crg wiki)                             │   │
│  │ 4. Load wiki content                                     │   │
│  │ 5. Store initial codebase hash                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Agent Turn Loop                             │   │
│  │                                                          │   │
│  │   User message ──► Planner                              │   │
│  │                          │                               │   │
│  │                          ▼                               │   │
│  │                   Check codebase hash                    │   │
│  │                          │                               │   │
│  │              ┌───────────┴───────────┐                   │   │
│  │              ▼                       ▼                   │   │
│  │         Hash changed?           Hash same?               │   │
│  │              │                       │                   │   │
│  │              ▼                       │                   │   │
│  │      Update KB (async)               │                   │   │
│  │              │                       │                   │   │
│  │              ▼                       │                   │   │
│  │   Replace old KB in messages          │                   │   │
│  │              │                       │                   │   │
│  │              └───────────────────────┘                   │   │
│  │                          │                               │   │
│  │                          ▼                               │   │
│  │                   Process message                        │   │
│  │                          │                               │   │
│  │                          ▼                               │   │
│  │                   Return to user                         │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Message History Example

```
Turn 1:
┌─────────────────────────────────────────────────────────────┐
│ System Prompt                                               │
│ "You are a coding agent.                                    │
│ <!-- KNOWLEDGE_BASE_START -->                               │
│ - auth.py has UserService class                             │
│ - payment.py handles checkout                               │
│ <!-- KNOWLEDGE_BASE_END -->                                 │
│ ...rules..."                                                │
├─────────────────────────────────────────────────────────────┤
│ User: "Tell me about auth"                                  │
│ Agent: "Based on the KB, auth has UserService..."           │
└─────────────────────────────────────────────────────────────┘

Turn 2 (Codebase changed, KB updated):
┌─────────────────────────────────────────────────────────────┐
│ System Prompt (REPLACED!)                                    │
│ "You are a coding agent.                                    │
│ <!-- KNOWLEDGE_BASE_START -->                               │
│ - auth.py has AuthService class  ← NEW KB!                  │
│ - payment.py handles checkout                               │
│ <!-- KNOWLEDGE_BASE_END -->                                 │
│ ...rules..."                                                │
├─────────────────────────────────────────────────────────────┤
│ User: "Tell me about auth"                                  │
│ Agent: "Based on the KB, auth has AuthService..."            │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing Plan

### Unit Tests

1. **HashChecker Tests**
   - Test git hash detection
   - Test file hash fallback
   - Test change detection

2. **KnowledgeBaseContextManager Tests**
   - Test KB wrapping with markers
   - Test message replacement
   - Test marker detection

3. **WikiKnowledgeManager Tests**
   - Test initialization flow
   - Test update mechanism
   - Test context refresh

### Integration Tests

1. **End-to-End Flow**
   - Start session with --crg
   - Verify knowledge base loaded
   - Modify file
   - Verify KB updated
   - Verify message history updated

---

## Configuration Reference

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `crg_enabled` | bool | False | Enable knowledge base feature |
| `crg_auto_build` | bool | True | Auto-build graph on start |
| `crg_check_hash_before_turn` | bool | True | Check hash before each turn |
| `crg_update_async` | bool | True | Update without blocking |
| `crg_wiki_dir` | str | ".code-review-graph/wiki" | Wiki output directory |
| `crg_context_max_chars` | int | 50000 | Max context size |
| `crg_include_sections` | List[str] | [...] | Wiki sections to include |

---

## CLI Usage Examples

```bash
# Start chat with knowledge base
liteagent chat --crg

# Start with specific provider and knowledge base
liteagent chat --provider nvidia --model llama3 --crg

# One-shot task with knowledge base
liteagent do "Explain the authentication flow" --crg

# Resume session with knowledge base
liteagent chat --resume last --crg
```

---

## Implementation Updates

### Auto-Build Improvements

The `initialize()` method now checks for multiple conditions before deciding to build:

| Condition | Action |
|-----------|--------|
| `.code-review-graph/` folder missing | Build graph |
| Wiki folder missing or empty | Generate wiki |
| Graph has 0 nodes | Build graph |
| Graph has 0 files indexed | Build graph |
| Status shows "not built" | Build graph |
| Status shows "never" updated | Build graph |

### Comprehensive Logging Events

All KB operations are logged to the session log file (`~/.liteagent/<session_id>.log`):

| Event | When | Data Logged |
|-------|------|-------------|
| `knowledge_base_init_start` | KB initialization starts | project_path, wiki_dir |
| `knowledge_base_init_success` | KB initialized successfully | nodes, edges, files, wiki_files, context_length, initial_hash |
| `knowledge_base_init_failed` | KB initialization fails | error, error_type |
| `knowledge_base_status_check` | Graph status checked | graph_folder_exists, wiki_folder_exists, nodes, edges, files |
| `knowledge_base_build_start` | Build starts | reason |
| `knowledge_base_build_end` | Build completes | build_output |
| `knowledge_base_wiki_start` | Wiki generation starts | reason |
| `knowledge_base_wiki_end` | Wiki generation ends | wiki_output |
| `knowledge_base_hash_unchanged` | Hash same, no update needed | hash, update_needed: false |
| `knowledge_base_hash_changed` | Hash changed, update needed | old_hash, new_hash, update_needed: true |
| `knowledge_base_update_start` | Update starts | - |
| `knowledge_base_update_success` | Update succeeds | nodes, edges, files, wiki_files, context_length |
| `knowledge_base_update_failed` | Update fails | error, error_type |
| `crg_command_start` | CRG command starts | command |
| `crg_command_success` | CRG command succeeds | command, output_length |
| `crg_command_error` | CRG command fails | command, error, returncode |

### Log File Location

Session logs are saved to:
```
~/.liteagent/<session_id>.log
```

Example: `C:\Users\<username>\.liteagent\46a4a477-3cb3-431f-85a9-d896824dbb55.log`

---

## Known Issues

### 1. Tool Calling May Fail with Large KB Context

**Problem**: When using smaller models (e.g., `qwen3.5:2b`) with a large knowledge base context, the model may fail to make proper tool calls. Instead, it outputs tool names as plain text.

**Symptoms**:
- Agent says it will call a tool but nothing happens
- Tool names appear as text in the response instead of actual tool calls
- Session ends without any tool execution

**Workarounds**:
1. Reduce KB context size in `.env`:
   ```
   CRG_CONTEXT_MAX_CHARS=10000
   ```

2. Use a larger/better model:
   ```bash
   liteagent chat --provider ollama -m llama3.2 --crg
   ```

3. Disable KB if tool calling issues persist:
   ```bash
   liteagent chat  # without --crg
   ```

**Status**: Under investigation. May need to restructure how KB context is injected into the system prompt.

---

## Future Enhancements

1. **Selective Loading**: Load only relevant wiki sections based on task
2. **Caching**: Cache wiki content between sessions
3. **Incremental Context**: Update context incrementally instead of full reload
4. **Multi-Project Support**: Handle multiple project knowledge bases
5. **Custom Wiki Templates**: Allow custom wiki generation templates
6. **Smart Context Sizing**: Automatically adjust KB context size based on model capabilities

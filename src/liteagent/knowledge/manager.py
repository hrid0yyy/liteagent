"""
Main knowledge base manager.

This module provides the main WikiKnowledgeManager class that coordinates
building, loading, and updating the knowledge base from code-review-graph.
"""

import asyncio
import shutil
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
        """
        Initialize the knowledge base manager.
        
        Args:
            project_path: Path to the project root
            wiki_dir: Path to wiki directory (default from settings)
            max_context_chars: Maximum context size in characters
        """
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
        1. Check if code-review-graph is available
        2. Check if graph folder exists
        3. Check if wiki folder exists and has content
        4. Check graph status (nodes, edges, files)
        5. Build if needed (missing folder, empty graph, etc.)
        6. Generate wiki if needed
        7. Load context
        8. Store initial hash
        
        Returns:
            True if initialization successful
        """
        try:
            # Step 1: Check if code-review-graph is available
            if not shutil.which("code-review-graph"):
                log_event("knowledge_base_init_failed", "manager", {
                    "success": False,
                    "reason": "code-review-graph not found in PATH"
                })
                return False
            
            log_event("knowledge_base_init_start", "manager", {
                "project_path": str(self.project_path),
                "wiki_dir": self.wiki_dir
            })
            
            # Step 2: Check if graph folder exists
            graph_dir = self.project_path / ".code-review-graph"
            graph_exists = graph_dir.exists()
            
            # Step 3: Check if wiki folder exists and has content
            wiki_exists = self.loader.wiki_exists()
            wiki_file_count = self.loader.get_file_count()
            
            # Step 4: Check graph status
            status = await self._run_crg_command("status")
            
            # Parse status for stats
            nodes = self._parse_status_value(status, "Nodes")
            edges = self._parse_status_value(status, "Edges")
            files = self._parse_status_value(status, "Files")
            
            log_event("knowledge_base_status_check", "manager", {
                "graph_folder_exists": graph_exists,
                "wiki_folder_exists": wiki_exists,
                "wiki_file_count": wiki_file_count,
                "nodes": nodes,
                "edges": edges,
                "files": files,
                "status_raw": status.strip()
            })
            
            # Step 5: Determine if build is needed
            needs_build = (
                not graph_exists or                    # No graph folder
                "not built" in status.lower() or       # Status says not built
                "never" in status.lower() or           # Never updated
                nodes == 0 or                          # Empty graph (no nodes)
                files == 0                             # No files indexed
            )
            
            # Step 6: Build if needed
            if settings.crg_auto_build and needs_build:
                log_event("knowledge_base_build_start", "manager", {
                    "reason": "graph_missing_or_empty" if not graph_exists or nodes == 0 else "status_indicates_rebuild"
                })
                build_output = await self._run_crg_command("build", timeout=300)
                log_event("knowledge_base_build_end", "manager", {
                    "build_output": build_output.strip()
                })
                
                # Re-check status after build
                status = await self._run_crg_command("status")
                nodes = self._parse_status_value(status, "Nodes")
                edges = self._parse_status_value(status, "Edges")
                files = self._parse_status_value(status, "Files")
            
            # Step 7: Generate wiki if needed
            wiki_exists = self.loader.wiki_exists()
            if not wiki_exists or wiki_file_count == 0:
                log_event("knowledge_base_wiki_start", "manager", {
                    "reason": "wiki_missing_or_empty"
                })
                wiki_output = await self._run_crg_command("wiki")
                log_event("knowledge_base_wiki_end", "manager", {
                    "wiki_output": wiki_output.strip()
                })
            
            # Step 8: Load context
            await self.refresh_context()
            
            # Step 9: Store initial hash
            self.hash_checker.update_stored_hash()
            initial_hash = self.hash_checker.get_stored_hash()
            
            self._initialized = True
            
            # Final success log with all stats
            wiki_file_count = self.loader.get_file_count()
            log_event("knowledge_base_init_success", "manager", {
                "success": True,
                "nodes": nodes,
                "edges": edges,
                "files": files,
                "wiki_files": wiki_file_count,
                "context_length": len(app_state.knowledge_base),
                "context_loaded": app_state.knowledge_base_loaded,
                "initial_hash": initial_hash
            })
            
            return True
            
        except Exception as e:
            log_error("manager", e, {"phase": "initialize"})
            log_event("knowledge_base_init_failed", "manager", {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            })
            return False
    
    def _parse_status_value(self, status: str, key: str) -> int:
        """Parse a value from the status output."""
        import re
        pattern = rf"{key}:\s*(\d+)"
        match = re.search(pattern, status, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0
    
    async def check_and_update(self) -> bool:
        """
        Check if codebase changed and update KB if needed.
        
        This should be called before each agent turn.
        
        Returns:
            True if KB was updated, False otherwise
        """
        if not self._initialized:
            log_event("knowledge_base_check_skipped", "manager", {
                "reason": "not_initialized"
            })
            return False
        
        old_hash = self.hash_checker.get_stored_hash()
        has_changed = self.hash_checker.has_changed()
        new_hash = self.hash_checker.get_stored_hash()
        
        if not has_changed:
            log_event("knowledge_base_hash_unchanged", "manager", {
                "hash": old_hash,
                "update_needed": False
            })
            return False
        
        log_event("knowledge_base_hash_changed", "manager", {
            "old_hash": old_hash,
            "new_hash": new_hash,
            "update_needed": True
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
            log_event("knowledge_base_update_start", "manager", {})
            
            # Incremental update (auto-detect from git)
            update_output = await self._run_crg_command("update", timeout=120)
            
            # Regenerate wiki
            wiki_output = await self._run_crg_command("wiki")
            
            # Refresh context
            await self.refresh_context()
            
            # Update stored hash
            self.hash_checker.update_stored_hash()
            new_hash = self.hash_checker.get_stored_hash()
            
            # Get updated stats
            status = await self._run_crg_command("status")
            nodes = self._parse_status_value(status, "Nodes")
            edges = self._parse_status_value(status, "Edges")
            files = self._parse_status_value(status, "Files")
            wiki_file_count = self.loader.get_file_count()
            
            log_event("knowledge_base_update_success", "manager", {
                "success": True,
                "new_hash": new_hash,
                "nodes": nodes,
                "edges": edges,
                "files": files,
                "wiki_files": wiki_file_count,
                "context_length": len(app_state.knowledge_base),
                "context_loaded": app_state.knowledge_base_loaded,
                "update_output": update_output.strip(),
                "wiki_output": wiki_output.strip()
            })
            
            return True
            
        except Exception as e:
            log_error("manager", e, {"phase": "update_graph"})
            log_event("knowledge_base_update_failed", "manager", {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            })
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
            "context_length": len(context),
            "wiki_files": len(wiki_content)
        })
        
        return context
    
    def _build_context(self, wiki_content: dict) -> str:
        """
        Build context string from wiki files.
        
        Args:
            wiki_content: Dictionary mapping filename to content
            
        Returns:
            Formatted context string
        """
        # Priority order for wiki sections
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
        """
        Format context for system prompt.
        
        Args:
            parts: List of formatted wiki sections
            
        Returns:
            Formatted context string
        """
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
        """
        Get the current knowledge base context.
        
        Returns:
            Current KB context string
        """
        return app_state.knowledge_base
    
    def is_initialized(self) -> bool:
        """
        Check if knowledge base is initialized.
        
        Returns:
            True if initialized
        """
        return self._initialized
    
    def is_available(self) -> bool:
        """
        Check if code-review-graph is available.
        
        Returns:
            True if the CLI tool is found
        """
        return shutil.which("code-review-graph") is not None
    
    async def _run_crg_command(self, args: str, timeout: int = 60) -> str:
        """
        Run a code-review-graph CLI command.
        
        Args:
            args: Command arguments (e.g., "build", "update", "wiki")
            timeout: Command timeout in seconds
            
        Returns:
            Command output
            
        Raises:
            RuntimeError: If command fails
        """
        cmd = f"code-review-graph {args}"
        
        log_event("crg_command_start", "manager", {"command": cmd})
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_path)
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except:
                pass
            raise RuntimeError(f"Command timed out after {timeout} seconds: {cmd}")
        
        if process.returncode != 0:
            error_msg = stderr.decode() or "Unknown error"
            log_event("crg_command_error", "manager", {
                "command": cmd,
                "error": error_msg,
                "returncode": process.returncode
            })
            raise RuntimeError(f"CRG command failed: {error_msg}")
        
        output = stdout.decode()
        log_event("crg_command_success", "manager", {
            "command": cmd,
            "output_length": len(output)
        })
        
        return output


# Global knowledge manager instance
_knowledge_manager: Optional[WikiKnowledgeManager] = None


def get_knowledge_manager() -> Optional[WikiKnowledgeManager]:
    """
    Get the global knowledge manager instance.
    
    Returns:
        WikiKnowledgeManager instance or None
    """
    return _knowledge_manager


def set_knowledge_manager(manager: WikiKnowledgeManager):
    """
    Set the global knowledge manager instance.
    
    Args:
        manager: WikiKnowledgeManager instance
    """
    global _knowledge_manager
    _knowledge_manager = manager


def create_knowledge_manager(project_path: str = ".") -> WikiKnowledgeManager:
    """
    Create a new knowledge manager instance.
    
    Args:
        project_path: Path to the project root
        
    Returns:
        New WikiKnowledgeManager instance
    """
    return WikiKnowledgeManager(project_path=project_path)

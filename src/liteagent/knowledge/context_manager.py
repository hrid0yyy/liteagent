"""
Knowledge base context management in message history.

This module provides utilities for managing knowledge base content in
the agent's message history, including wrapping content with markers
and replacing old content when the knowledge base is updated.
"""

import re
from typing import List, Dict, Any


class KnowledgeBaseContextManager:
    """
    Manages KB content in message history.
    
    Uses markers to identify KB content, allowing replacement
    when the knowledge base is updated. This prevents context
    pollution from outdated knowledge base content.
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
        """
        Check if content contains KB markers.
        
        Args:
            content: Content to check
            
        Returns:
            True if both start and end markers are present
        """
        return cls.KB_START_MARKER in content and cls.KB_END_MARKER in content
    
    @classmethod
    def extract_kb(cls, content: str) -> str:
        """
        Extract KB content from marked section.
        
        Args:
            content: Content containing KB markers
            
        Returns:
            Content between markers, or empty string if not found
        """
        pattern = f"{re.escape(cls.KB_START_MARKER)}(.*?){re.escape(cls.KB_END_MARKER)}"
        match = re.search(pattern, content, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    @classmethod
    def remove_kb(cls, content: str) -> str:
        """
        Remove KB content from a message.
        
        Args:
            content: Content containing KB markers
            
        Returns:
            Content with KB section removed
        """
        pattern = f"{re.escape(cls.KB_START_MARKER)}.*?{re.escape(cls.KB_END_MARKER)}"
        return re.sub(pattern, "", content, flags=re.DOTALL).strip()
    
    @classmethod
    def get_kb_length(cls, content: str) -> int:
        """
        Get the length of KB content in a message.
        
        Args:
            content: Content containing KB markers
            
        Returns:
            Length of KB content, or 0 if not found
        """
        kb = cls.extract_kb(content)
        return len(kb)

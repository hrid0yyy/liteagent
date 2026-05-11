from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseProvider(ABC):
    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def get_tool_schema(self, tool_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a standard tool definition to the provider's specific schema."""
        pass

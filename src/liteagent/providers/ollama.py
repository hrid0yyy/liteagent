import httpx
from typing import List, Dict, Any, Optional
from .base import BaseProvider
from ..core.config import settings

class OllamaProvider(BaseProvider):
    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or settings.default_model
        self.base_url = base_url or settings.ollama_base_url

    async def generate(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
            }
            if tools:
                payload["tools"] = tools
            
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]

    def get_tool_schema(self, tool_definition: Dict[str, Any]) -> Dict[str, Any]:
        # Ollama follows OpenAI-like tool schema
        return {
            "type": "function",
            "function": tool_definition
        }

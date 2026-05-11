import httpx
from typing import List, Dict, Any, Optional
from .base import BaseProvider
from ..core.config import settings

class NvidiaNimProvider(BaseProvider):
    def __init__(self, model: str = None, api_key: str = None):
        # Default to the requested model
        self.model = model or "minimaxai/minimax-m2.5"
        self.api_key = api_key or settings.nvidia_api_key
        self.base_url = "https://integrate.api.nvidia.com/v1"

    async def generate(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("NVIDIA API key is required. Set NVIDIA_API_KEY in your .env file.")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.5,
                "top_p": 1,
                "max_tokens": 1024,
                "stream": False,
            }
            if tools:
                payload["tools"] = tools
            
            response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            
            if response.status_code != 200:
                error_msg = f"NVIDIA API Error ({response.status_code}): {response.text}"
                raise Exception(error_msg)
                
            data = response.json()
            return data["choices"][0]["message"]

    def get_tool_schema(self, tool_definition: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": tool_definition
        }

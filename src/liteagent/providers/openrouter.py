import httpx
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from .base import BaseProvider
from ..core.config import settings
from ..core.logger import log_event, log_error
from ..cli.formatter import console

def should_retry(exception):
    """Return True if we should retry based on the exception."""
    msg = str(exception)
    # Retry on 429, 5xx, or network timeouts/errors
    return any(code in msg for code in ["429", "500", "502", "503", "504"]) or \
           any(err in msg for err in ["ReadTimeout", "ConnectError", "Network Error"])

class OpenRouterProvider(BaseProvider):
    def __init__(self, model: str = None, api_key: str = None):
        self.model = model or "minimax/minimax-m2.5:free"
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = "https://openrouter.ai/api/v1"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception(should_retry),
        reraise=True
    )
    async def generate(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY in your .env file.")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/liteagent/liteagent",
            "X-Title": "LiteAgent"
        }
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.5,
                    "top_p": 1,
                }
                if tools:
                    payload["tools"] = tools
                log_event(
                    "provider_request",
                    "provider.openrouter",
                    {"url": f"{self.base_url}/chat/completions", "payload": payload},
                )
                
                response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                
                if response.status_code == 429:
                    console.print("[yellow]Warning: Rate limit reached (OpenRouter 429). Retrying...[/yellow]")
                    log_event(
                        "provider_retry",
                        "provider.openrouter",
                        {"status_code": response.status_code, "response_text": response.text},
                        level="warn",
                    )
                    raise Exception(f"Rate Limit Error (429): {response.text}")
                    
                if response.status_code != 200:
                    error_msg = f"OpenRouter API Error ({response.status_code}): {response.text}"
                    log_error(
                        "provider.openrouter",
                        error_msg,
                        {"status_code": response.status_code, "response_text": response.text, "payload": payload},
                    )
                    raise Exception(error_msg)
                    
                data = response.json()
                log_event("provider_response", "provider.openrouter", {"status_code": response.status_code, "response_json": data})
                return data["choices"][0]["message"]
        except (httpx.ReadTimeout, httpx.ConnectError) as e:
            console.print(f"[yellow]Warning: Network error ({str(e)}). Retrying...[/yellow]")
            log_error("provider.openrouter", e, {"stage": "network_exception"})
            raise Exception(f"Network Error: {str(e)}")

    def get_tool_schema(self, tool_definition: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": tool_definition
        }

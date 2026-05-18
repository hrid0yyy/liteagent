from .config import settings
from .logger import log_event, log_error

def _get_summarizer_provider():
    provider_name = settings.summarizer_provider
    model = settings.summarizer_model
    
    if provider_name == "ollama":
        from ..providers.ollama import OllamaProvider
        return OllamaProvider(model=model)
    elif provider_name == "nvidia":
        from ..providers.nvidia_nim import NvidiaNimProvider
        return NvidiaNimProvider(model=model)
    elif provider_name == "openrouter":
        from ..providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(model=model)
    else:
        raise ValueError(f"Unsupported summarizer provider: {provider_name}")

async def summarize_payload(tool_name: str, tool_description: str, payload: str) -> str:
    """Summarizes a massive tool payload using a fast local model."""
    try:
        provider = _get_summarizer_provider()
        
        system_prompt = (
            f"You are an internal data extraction node for an autonomous coding agent.\n"
            f"You have received a massive raw output payload from the tool '{tool_name}'.\n\n"
            f"The main agent expects this tool to do the following:\n"
            f"\"{tool_description}\"\n\n"
            f"Your goal is to extract and compress the raw payload so the main agent gets exactly what it expects.\n"
            f"Do NOT hallucinate. Keep the response as a dense, bulleted summary."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"PAYLOAD TO SUMMARIZE:\n{payload}"}
        ]
        
        result = await provider.generate(messages=messages)
        
        # The provider returns the message dict directly
        content = result.get("content", "")
        
        if not content:
            return "Summarizer returned empty response. (Raw payload omitted for size)"
            
        return content
        
    except Exception as e:
        log_error("summarizer", e, {"tool": tool_name})
        # If the summarizer fails, it's safer to return a truncated version of the raw payload
        return f"[Summarizer Failed] Truncated Raw Payload:\n\n{payload[:2000]}..."

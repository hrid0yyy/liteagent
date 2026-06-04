from typing import Optional
from .base import BaseProvider
from .ollama import OllamaProvider
from .nvidia_nim import NvidiaNimProvider
from .openrouter import OpenRouterProvider
from .github import GitHubModelsProvider

class LLMProviderFactory:
    """Factory for instantiating LLM providers."""
    
    @staticmethod
    def create_provider(provider_name: str, model: Optional[str] = None) -> BaseProvider:
        name = provider_name.lower()
        if name == "ollama":
            return OllamaProvider(model=model)
        elif name == "nvidia":
            return NvidiaNimProvider(model=model)
        elif name == "openrouter":
            return OpenRouterProvider(model=model)
        elif name == "github":
            return GitHubModelsProvider(model=model)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

import warnings

# Suppress LangChain/LangGraph warnings globally
try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
    warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
except ImportError:
    pass

warnings.filterwarnings("ignore", category=UserWarning)

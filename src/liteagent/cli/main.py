import asyncio
import typer
import warnings
from typing import Optional
from rich.prompt import Prompt
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from ..core.config import settings
from ..core.state import app_state
from ..providers.ollama import OllamaProvider
from ..providers.nvidia_nim import NvidiaNimProvider
from ..providers.openrouter import OpenRouterProvider
from ..graph.builder import create_graph
from .formatter import format_message, format_tool_output, console
from .server import start_server

# Suppress annoying dependency warnings
warnings.filterwarnings("ignore", category=UserWarning)
try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
    warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
except ImportError:
    pass

app = typer.Typer(help="LiteAgent: A lightweight coding agent CLI.")

@app.command()
def do(
    task: str = typer.Argument(..., help="The task for the agent to perform."),
    provider_name: str = typer.Option(settings.default_provider, "--provider", "-p", help="LLM provider to use."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name to use.")
):
    """Run a single task using the agent."""
    asyncio.run(_run_task(task, provider_name, model))

@app.command()
def chat(
    provider_name: str = typer.Option(settings.default_provider, "--provider", "-p", help="LLM provider to use."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name to use.")
):
    """Open an interactive chat session with the agent."""
    asyncio.run(_run_chat(provider_name, model))

async def _run_task(task: str, provider_name: str, model: Optional[str]):
    provider = _get_provider(provider_name, model)
    graph = create_graph(provider)
    
    state = {
        "messages": [{"role": "user", "content": task}],
        "plan": "",
        "tool_outputs": [],
        "errors": [],
        "is_complete": False
    }

    console.print(Panel(f"Starting task: {task}", title="LiteAgent", expand=False))
    await _execute_graph(graph, state, verbose=False)
    console.print("\n[bold green]Task processing finished.[/bold green]")

async def _run_chat(provider_name: str, model: Optional[str]):
    provider = _get_provider(provider_name, model)
    graph = create_graph(provider)
    
    state = {
        "messages": [],
        "plan": "",
        "tool_outputs": [],
        "errors": [],
        "is_complete": False
    }

    console.print(Panel("Interactive Chat Started. Type 'exit' or 'quit' to end.", title="LiteAgent Chat", expand=False))

    # Start the web tool inspector in the background
    asyncio.create_task(start_server())
    console.print("[bold cyan]🌐 Tool Inspector running at http://localhost:8000[/bold cyan]")

    kb = KeyBindings()

    @kb.add("s-tab")
    def _(event):
        app_state.auto_mode = not app_state.auto_mode
        # Refresh the prompt to update the toolbar
        event.app.invalidate()

    def get_toolbar():
        mode = "AUTO" if app_state.auto_mode else "MANUAL"
        color = "green" if app_state.auto_mode else "yellow"
        return f" Mode: {mode} (Shift+Tab to toggle) | exit to quit"

    session = PromptSession(key_bindings=kb, bottom_toolbar=get_toolbar)

    while True:
        try:
            user_input = await session.prompt_async("\nYou > ")
        except EOFError:
            break
            
        if user_input.lower() in ["exit", "quit"]:
            break
        
        state["messages"].append({"role": "user", "content": user_input})
        state["is_complete"] = False
        
        state = await _execute_graph(graph, state, verbose=False)

def _get_provider(provider_name: str, model: Optional[str]):
    if provider_name == "ollama":
        return OllamaProvider(model=model)
    elif provider_name == "nvidia":
        return NvidiaNimProvider(model=model)
    elif provider_name == "openrouter":
        return OpenRouterProvider(model=model)
    else:
        console.print(f"[red]Error:[/red] Unsupported provider: {provider_name}")
        raise typer.Exit(1)

async def _execute_graph(graph, state, verbose=False):
    current_state = state
    async for event in graph.astream(state):
        for node_name, node_state in event.items():
            # In ReAct, the core node is 'agent'
            if "messages" in node_state:
                for msg in node_state["messages"]:
                    if msg.get("role") == "user":
                        continue
                    format_message(msg)
            
            if "errors" in node_state and node_state["errors"]:
                for err in node_state["errors"]:
                    console.print(f"[red]Error:[/red] {err}")

            if "tool_outputs" in node_state and node_state["tool_outputs"]:
                for out in node_state["tool_outputs"]:
                    format_tool_output(out)
             
            # Merge state updates
            for key, value in node_state.items():
                if key == "messages":
                    current_state["messages"].extend(value)
                else:
                    current_state[key] = value
    
    return current_state

if __name__ == "__main__":
    app()

import asyncio
import typer
import warnings
from typing import Optional
from rich.prompt import Prompt
from rich.panel import Panel
from ..core.config import settings
from ..providers.ollama import OllamaProvider
from ..providers.nvidia_nim import NvidiaNimProvider
from ..graph.builder import create_graph
from .formatter import format_message, console

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
    
    # We keep the message history persistent in this 'state' variable
    state = {
        "messages": [],
        "plan": "",
        "tool_outputs": [],
        "errors": [],
        "is_complete": False
    }

    console.print(Panel("Interactive Chat Started. Type 'exit' or 'quit' to end.", title="LiteAgent Chat", expand=False))

    while True:
        user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
        if user_input.lower() in ["exit", "quit"]:
            break
        
        # Add the new message to state.
        state["messages"].append({"role": "user", "content": user_input})
        state["is_complete"] = False
        
        # Run the graph and update the persistent state
        state = await _execute_graph(graph, state, verbose=False)

def _get_provider(provider_name: str, model: Optional[str]):
    if provider_name == "ollama":
        return OllamaProvider(model=model)
    elif provider_name == "nvidia":
        return NvidiaNimProvider(model=model)
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
            
            # Merge state updates
            for key, value in node_state.items():
                if key == "messages":
                    current_state["messages"].extend(value)
                else:
                    current_state[key] = value
    
    return current_state

if __name__ == "__main__":
    app()

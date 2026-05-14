import asyncio
import os
import typer
import uuid
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
from ..core.logger import start_session_logger, end_session_logger, log_event, log_error
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
    session_id = str(uuid.uuid4())
    app_state.session_id = session_id
    app_state.turn_index = 1
    app_state.tool_call_count = 0
    app_state.error_count = 0
    app_state.session_log_path = start_session_logger(
        session_id=session_id,
        mode="do",
        provider=provider_name,
        model=getattr(provider, "model", model or ""),
        cwd=os.getcwd(),
    )
    graph = create_graph(provider)
    
    state = {
        "messages": [{"role": "user", "content": task}],
        "plan": "",
        "tool_outputs": [],
        "errors": [],
        "is_complete": False
    }
    log_event("user_input", "cli", {"content": task}, turn_index=app_state.turn_index)

    console.print(Panel(f"Starting task: {task}", title="LiteAgent", expand=False))
    try:
        await _execute_graph(graph, state, verbose=False)
    except Exception as e:
        app_state.error_count += 1
        log_error("cli", e, {"phase": "run_task"}, turn_index=app_state.turn_index)
        raise
    finally:
        end_session_logger({
            "turn_count": app_state.turn_index,
            "tool_call_count": app_state.tool_call_count,
            "error_count": app_state.error_count,
        })
    console.print("\n[bold green]Task processing finished.[/bold green]")

async def _run_chat(provider_name: str, model: Optional[str]):
    provider = _get_provider(provider_name, model)
    session_id = str(uuid.uuid4())
    app_state.session_id = session_id
    app_state.turn_index = 0
    app_state.tool_call_count = 0
    app_state.error_count = 0
    app_state.session_log_path = start_session_logger(
        session_id=session_id,
        mode="chat",
        provider=provider_name,
        model=getattr(provider, "model", model or ""),
        cwd=os.getcwd(),
    )
    graph = create_graph(provider)
    
    state = {
        "messages": [],
        "plan": "",
        "tool_outputs": [],
        "errors": [],
        "is_complete": False
    }

    console.print(Panel("Interactive Chat Started. Type 'exit' or 'quit' to end.", title="LiteAgent Chat", expand=False))

    # Start tool inspector with dynamic port fallback
    inspector_info = await start_server(
        host=settings.inspector_host,
        preferred_port=settings.inspector_port,
        search_limit=settings.inspector_port_search_limit,
    )
    inspector_task = inspector_info.get("task")
    if inspector_info.get("started"):
        inspector_url = f"http://{inspector_info['host']}:{inspector_info['port']}"
        console.print(f"[bold cyan]🌐 Tool Inspector running at {inspector_url}[/bold cyan]")
        log_event("inspector_ready", "cli", {"url": inspector_url}, turn_index=app_state.turn_index)
    else:
        reason = inspector_info.get("reason", "unknown")
        console.print(f"[bold yellow]⚠ Tool Inspector unavailable ({reason}). Chat continues.[/bold yellow]")
        log_event("inspector_unavailable", "cli", inspector_info, level="warn", turn_index=app_state.turn_index)

    kb = KeyBindings()

    @kb.add("s-tab")
    def _(event):
        app_state.auto_mode = not app_state.auto_mode
        log_event("mode_toggle", "cli", {"auto_mode": app_state.auto_mode}, turn_index=app_state.turn_index)
        # Refresh the prompt to update the toolbar
        event.app.invalidate()

    def get_toolbar():
        mode = "AUTO" if app_state.auto_mode else "MANUAL"
        color = "green" if app_state.auto_mode else "yellow"
        return f" Mode: {mode} (Shift+Tab to toggle) | exit to quit"

    session = PromptSession(key_bindings=kb, bottom_toolbar=get_toolbar)

    try:
        while True:
            try:
                user_input = await session.prompt_async("\nYou > ")
            except EOFError:
                log_event("chat_eof", "cli", {}, turn_index=app_state.turn_index)
                break
                
            if user_input.lower() in ["exit", "quit"]:
                log_event("chat_exit", "cli", {"command": user_input}, turn_index=app_state.turn_index)
                break
            
            app_state.turn_index += 1
            state["messages"].append({"role": "user", "content": user_input})
            state["is_complete"] = False
            log_event("user_input", "cli", {"content": user_input}, turn_index=app_state.turn_index)
            
            try:
                state = await _execute_graph(graph, state, verbose=False)
            except Exception as e:
                app_state.error_count += 1
                log_error("cli", e, {"phase": "chat_loop"}, turn_index=app_state.turn_index)
                raise
    finally:
        end_session_logger({
            "turn_count": app_state.turn_index,
            "tool_call_count": app_state.tool_call_count,
            "error_count": app_state.error_count,
        })

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
    log_event("graph_execute_start", "cli", {"verbose": verbose}, turn_index=app_state.turn_index)
    async for event in graph.astream(state):
        log_event("graph_event", "cli", {"event": event}, turn_index=app_state.turn_index)
        for node_name, node_state in event.items():
            log_event("node_state", "cli", {"node": node_name, "state": node_state}, turn_index=app_state.turn_index)
            # In ReAct, the core node is 'agent'
            if "messages" in node_state:
                for msg in node_state["messages"]:
                    if msg.get("role") == "user":
                        continue
                    format_message(msg)
                    log_event("assistant_message", "cli", {"node": node_name, "message": msg}, turn_index=app_state.turn_index)
            
            if "errors" in node_state and node_state["errors"]:
                for err in node_state["errors"]:
                    console.print(f"[red]Error:[/red] {err}")
                    app_state.error_count += 1
                    log_event("node_error", "cli", {"node": node_name, "error": err}, level="error", turn_index=app_state.turn_index)

            if "tool_outputs" in node_state and node_state["tool_outputs"]:
                for out in node_state["tool_outputs"]:
                    format_tool_output(out)
                    app_state.tool_call_count += 1
                    log_event("tool_output", "cli", {"node": node_name, "tool_output": out}, turn_index=app_state.turn_index)
              
            # Merge state updates
            for key, value in node_state.items():
                if key == "messages":
                    current_state["messages"].extend(value)
                else:
                    current_state[key] = value
    
    log_event("graph_execute_end", "cli", {}, turn_index=app_state.turn_index)
    return current_state

if __name__ == "__main__":
    app()

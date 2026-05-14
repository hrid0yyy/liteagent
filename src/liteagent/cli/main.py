import asyncio
import os
import typer
import uuid
import warnings
from datetime import datetime
from typing import Optional
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table
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
from ..core.session import session_service

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
    task: str = typer.Argument(None, help="The task for the agent to perform."),
    provider_name: str = typer.Option(settings.default_provider, "--provider", "-p", help="LLM provider to use."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name to use."),
    resume: Optional[str] = typer.Option(None, "--resume", "-r", help="Resume a session by ID or 'last'."),
    inspector: bool = typer.Option(False, "--inspector", "-i", help="Enable tool inspector.")
):
    """Run a single task using the agent."""
    try:
        asyncio.run(_run_task(task, provider_name, model, resume, inspector))
    except KeyboardInterrupt:
        pass

@app.command()
def chat(
    provider_name: str = typer.Option(settings.default_provider, "--provider", "-p", help="LLM provider to use."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name to use."),
    resume: Optional[str] = typer.Option(None, "--resume", "-r", help="Resume a session by ID or 'last'."),
    inspector: bool = typer.Option(False, "--inspector", "-i", help="Enable tool inspector.")
):
    """Open an interactive chat session with the agent."""
    try:
        asyncio.run(_run_chat(provider_name, model, resume, inspector))
    except KeyboardInterrupt:
        pass

async def _select_session() -> Optional[str]:
    sessions = session_service.list_sessions()
    if not sessions:
        console.print("[yellow]No previous sessions found.[/yellow]")
        return None
    
    table = Table(title="Recent Sessions")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Session ID", style="magenta")
    table.add_column("Last Activity", style="green")
    
    for i, s in enumerate(sessions[:10]):
        dt = datetime.fromtimestamp(s["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(str(i+1), s["id"], dt)
    
    console.print(table)
    choice = Prompt.ask("Select a session to resume (enter # or ID)", default="1")
    
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            return sessions[idx]["id"]
    
    # Check if choice is an ID
    for s in sessions:
        if s["id"] == choice:
            return s["id"]
            
    return None

async def _run_task(task: str, provider_name: str, model: Optional[str], resume: Optional[str], inspector: bool = True):
    session_id = None
    state = None
    
    if resume:
        if resume == "last":
            sessions = session_service.list_sessions()
            session_id = sessions[0]["id"] if sessions else None
        else:
            session_id = resume
            
        if session_id:
            state = session_service.load_session(session_id)
            if not state:
                console.print(f"[red]Error:[/red] Session {session_id} not found.")
                return

    if not state:
        if not task:
            console.print("[red]Error:[/red] task is required when not resuming.")
            return
        session_id = str(uuid.uuid4())
        state = {
            "messages": [{"role": "user", "content": task}],
            "plan": "",
            "tool_outputs": [],
            "errors": [],
            "is_complete": False
        }
    
    provider = _get_provider(provider_name, model)
    app_state.session_id = session_id
    app_state.turn_index = len([m for m in state["messages"] if m["role"] == "user"])
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

    if resume:
        console.print(Panel(f"Resuming session: {session_id}", title="LiteAgent", expand=False))
        for msg in state["messages"]:
            format_message(msg)
    else:
        console.print(Panel(f"Starting task: {task}", title="LiteAgent", expand=False))
    
    try:
        await _execute_graph(graph, state, verbose=False)
        session_service.save_session(session_id, state)
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

async def _run_chat(provider_name: str, model: Optional[str], resume: Optional[str], inspector: bool = True):
    session_id = None
    state = None
    
    if resume:
        if resume == "last":
            sessions = session_service.list_sessions()
            session_id = sessions[0]["id"] if sessions else None
        elif resume == "select":
            session_id = await _select_session()
        else:
            session_id = resume
            
        if session_id:
            state = session_service.load_session(session_id)
            if not state:
                console.print(f"[red]Error:[/red] Session {session_id} not found.")
                return

    if not state:
        session_id = str(uuid.uuid4())
        state = {
            "messages": [],
            "plan": "",
            "tool_outputs": [],
            "errors": [],
            "is_complete": False
        }

    provider = _get_provider(provider_name, model)
    app_state.session_id = session_id
    app_state.turn_index = len([m for m in state["messages"] if m["role"] == "user"])
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

    if resume:
        console.print(Panel(f"Resuming session: {session_id}", title="LiteAgent Chat", expand=False))
        for msg in state["messages"]:
            format_message(msg)
    else:
        console.print(Panel("Interactive Chat Started. Type 'exit' or 'quit' to end.", title="LiteAgent Chat", expand=False))

    # Start tool inspector with dynamic port fallback
    inspector_task = None
    inspector_server = None
    if inspector:
        inspector_info = await start_server(
            host=settings.inspector_host,
            preferred_port=settings.inspector_port,
            search_limit=settings.inspector_port_search_limit,
        )
        inspector_task = inspector_info.get("task")
        inspector_server = inspector_info.get("server")
        if inspector_info.get("started"):
            inspector_url = f"http://{inspector_info['host']}:{inspector_info['port']}"
            console.print(f"[bold cyan]Tool Inspector running at {inspector_url}[/bold cyan]")
            log_event("inspector_ready", "cli", {"url": inspector_url}, turn_index=app_state.turn_index)
        else:
            reason = inspector_info.get("reason", "unknown")
            console.print(f"[bold yellow]Tool Inspector unavailable ({reason}). Chat continues.[/bold yellow]")
            log_event("inspector_unavailable", "cli", inspector_info, level="warn", turn_index=app_state.turn_index)

    kb = KeyBindings()

    @kb.add("s-tab")
    def _(event):
        app_state.auto_mode = not app_state.auto_mode
        log_event("mode_toggle", "cli", {"auto_mode": app_state.auto_mode}, turn_index=app_state.turn_index)
        # Refresh the prompt to update the toolbar
        event.app.invalidate()

    @kb.add("escape")
    def _(event):
        event.app.exit()

    def get_toolbar():
        mode = "AUTO" if app_state.auto_mode else "MANUAL"
        return f" Mode: {mode} (Shift+Tab to toggle) | Esc to quit"

    session = PromptSession(key_bindings=kb, bottom_toolbar=get_toolbar)

    try:
        while True:
            try:
                user_input = await session.prompt_async("\nYou > ")
            except EOFError:
                break
            except KeyboardInterrupt:
                # Catch interrupt during prompt
                break
                
            if user_input.lower() in ["exit", "quit"]:
                break
            
            app_state.turn_index += 1
            state["messages"].append({"role": "user", "content": user_input})
            state["is_complete"] = False
            log_event("user_input", "cli", {"content": user_input}, turn_index=app_state.turn_index)

            current_task = None
            try:
                current_task = asyncio.create_task(_execute_graph(graph, state, verbose=False))
                state = await current_task
                session_service.save_session(session_id, state)
            except asyncio.CancelledError:
                pass
            except KeyboardInterrupt:
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await asyncio.wait([current_task], timeout=1)
                    except:
                        pass
                console.print("\n[yellow]Interrupted. Session saved.[/yellow]")
            except Exception as e:
                app_state.error_count += 1
                log_error("cli", e, {"phase": "chat_loop"}, turn_index=app_state.turn_index)
                console.print(f"[red]Error:[/red] {type(e).__name__}: {e}")
                console.print("[yellow]You can try again or type 'exit' to quit.[/yellow]")
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        console.print("\n[bold yellow]Exiting LiteAgent...[/bold yellow]")
        if current_task and not current_task.done():
            current_task.cancel()
            try:
                await asyncio.wait([current_task], timeout=0.5)
            except:
                pass
        if inspector_server and inspector_task and not inspector_task.done():
            try:
                await asyncio.wait_for(inspector_server.shutdown(), timeout=1.0)
            except Exception:
                pass
        
        end_session_logger({
            "turn_count": app_state.turn_index,
            "tool_call_count": app_state.tool_call_count,
            "error_count": app_state.error_count,
        })
        console.print(f"Session saved. To resume: [bold cyan]liteagent chat --resume {session_id}[/bold cyan]")

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
    
    # Run the graph stream in a task so it can be cancelled
    execution_task = asyncio.create_task(_run_stream(graph, state, current_state))
    
    try:
        await execution_task
    except asyncio.CancelledError:
        console.print("\n[bold red]Execution cancelled by user.[/bold red]")
        # We don't re-raise here because we want to return the current state
        # The executor node should have already injected a "Cancelled" message if it was in a tool call
    except Exception as e:
        log_error("cli", e, {"phase": "execute_graph"})
        raise
    
    log_event("graph_execute_end", "cli", {}, turn_index=app_state.turn_index)
    return current_state

async def _run_stream(graph, state, current_state):
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

if __name__ == "__main__":
    app()

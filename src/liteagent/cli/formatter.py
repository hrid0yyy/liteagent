from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from typing import Optional

console = Console()

class LiveStreamHandler:
    def __init__(self, title: str = "Execution Log"):
        self.lines = []
        self.title = title
        self.max_lines = 15
        self.panel = Panel("", title=f"[bold cyan]{title}[/bold cyan]", border_style="cyan")
        self.live: Optional[Live] = None

    def start(self):
        self.live = Live(self.panel, console=console, refresh_per_second=10, transient=True)
        self.live.start()

    def update(self, line: str):
        self.lines.append(line)
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)
        
        content = "\n".join(self.lines)
        self.panel.renderable = Text.from_markup(content)
        if self.live:
            self.live.update(self.panel)

    def stop(self):
        if self.live:
            self.live.stop()
            self.live = None

_active_live_handler: Optional[LiveStreamHandler] = None

def start_live_stream(title: str = "Execution Log") -> LiveStreamHandler:
    global _active_live_handler
    if _active_live_handler:
        _active_live_handler.stop()
    
    _active_live_handler = LiveStreamHandler(title)
    _active_live_handler.start()
    return _active_live_handler

def stop_live_stream():
    global _active_live_handler
    if _active_live_handler:
        _active_live_handler.stop()
        _active_live_handler = None

def format_message(message: dict, show_thinking: bool = True):
    role = message.get("role", "unknown")
    content = message.get("content", "")
    tool_calls = message.get("tool_calls", [])
    
    if role == "user":
        console.print(f"\n[bold blue]You:[/bold blue] {content}")
        
    elif role == "assistant":
        # Content in assistant message often represents reasoning/thinking
        if content and tool_calls and show_thinking:
            console.print(Panel(content, title="[italic]Thinking[/italic]", border_style="dim"))
        
        if tool_calls:
            import json
            for call in tool_calls:
                func = call.get("function", call)
                name = func.get("name", "unknown")
                args_raw = func.get("arguments", "")
                
                # Parse arguments
                args = {}
                if isinstance(args_raw, str) and args_raw.strip():
                    try:
                        args = json.loads(args_raw)
                    except:
                        pass
                elif isinstance(args_raw, dict):
                    args = args_raw

                # Build context string
                context = ""
                if name == "read_file":
                    paths = args.get("file_paths", [])
                    if isinstance(paths, list):
                        context = ", ".join(paths)
                    else:
                        context = str(paths)
                elif name in {"write_file", "modify_file"}:
                    context = args.get("file_path", "")
                elif name == "list_files":
                    pattern = args.get("pattern", "")
                    dir_path = args.get("dir_path", ".")
                    context = f"'{pattern}' in {dir_path}"
                elif name == "search_in_files":
                    pattern = args.get("pattern", "")
                    dir_path = args.get("dir_path", ".")
                    context = f"'{pattern}' in {dir_path}"
                elif name == "rename_path":
                    old = args.get("old_path", "")
                    new = args.get("new_path", "")
                    context = f"{old} -> {new}"
                elif name == "delete_path":
                    context = args.get("path_to_delete", "")
                elif name == "run_shell_command":
                    context = args.get("command", "")
                
                display_name = f"[cyan]{name}[/cyan]"
                if context:
                    display_name += f" [dim]({context})[/dim]"
                
                console.print(f"  [bold yellow]🔧 Tool:[/bold yellow] {display_name}")
        
        # If it's a final answer (no tools)
        if content and not tool_calls:
            console.print(f"[bold green]Agent:[/bold green] {content}")
            
    elif role == "tool":
        # Raw tool output hidden to keep chat clean
        pass

def format_tool_output(tool_output: dict):
    name = tool_output.get("name")
    if name not in {"write_file", "modify_file"}:
        return

    diffs = tool_output.get("diffs", [])
    for item in diffs:
        path = item.get("path", "unknown")
        diff = item.get("diff", "")
        if not diff:
            continue

        console.print(f"[bold]Diff[/bold] [cyan]{path}[/cyan]")
        for line in diff.splitlines():
            if line.startswith("@@"):
                console.print(line, style="cyan", markup=False)
            elif line.startswith("+++ ") or line.startswith("--- "):
                console.print(line, style="bold", markup=False)
            elif line.startswith("+"):
                console.print(line, style="green", markup=False)
            elif line.startswith("-"):
                console.print(line, style="red", markup=False)
            else:
                console.print(line, style="dim", markup=False)

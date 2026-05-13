from rich.console import Console
from rich.panel import Panel

console = Console()

def format_message(message: dict, show_thinking: bool = True):
    role = message.get("role", "unknown")
    content = message.get("content", "")
    tool_calls = message.get("tool_calls", [])
    
    if role == "user":
        # Handled in main.py loop for chat
        pass
        
    elif role == "assistant":
        # Content in assistant message often represents reasoning/thinking
        if content and tool_calls and show_thinking:
            console.print(Panel(content, title="[italic]Thinking[/italic]", border_style="dim"))
        
        if tool_calls:
            for call in tool_calls:
                func = call.get("function", call)
                args = func.get("arguments", "")
                console.print(f"  [bold yellow]🔧 Tool:[/bold yellow] [cyan]{func['name']}[/cyan]")
        
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

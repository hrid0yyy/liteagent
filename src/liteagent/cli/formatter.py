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

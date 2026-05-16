from rich.console import Console
from rich.panel import Panel
from rich.box import SIMPLE
from rich.markdown import Markdown
from pathlib import Path

console = Console()

MAX_LINES = 200


def render_markdown(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        console.print(f"[dim]File not found: {file_path}[/dim]")
        return

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[dim]Error reading file: {e}[/dim]")
        return

    if not content.strip():
        console.print(f"[dim]Empty file: {file_path}[/dim]")
        return

    lines = content.splitlines()
    if len(lines) > MAX_LINES:
        content = "\n".join(lines[:MAX_LINES])
        truncated = True
    else:
        truncated = False

    output = Markdown(content)

    console.print(Panel(
        output,
        title=f"[bold cyan]{path.name}[/bold cyan]",
        border_style="cyan",
        box=SIMPLE,
        expand=False
    ))

    if truncated:
        console.print(f"[dim](Showing first {MAX_LINES} lines, file truncated)[/dim]")

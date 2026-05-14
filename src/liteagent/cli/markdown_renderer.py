import re
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import SIMPLE
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

    output = render_markdown_text(content)

    console.print(Panel(
        output,
        title=f"[bold cyan]{path.name}[/bold cyan]",
        border_style="cyan",
        box=SIMPLE,
        expand=False
    ))

    if truncated:
        console.print(f"[dim](Showing first {MAX_LINES} lines, file truncated)[/dim]")


def render_markdown_text(md_text: str) -> Text:
    result = Text()
    in_code_block = False
    code_lang = ""
    code_lines = []

    for line in md_text.splitlines():
        if line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line[3:].strip()
                code_lines = []
                result.append(line + "\n", style="dim")
            else:
                in_code_block = False
                result.append("```\n", style="dim")
            continue

        if in_code_block:
            code_lines.append(line)
            result.append(line + "\n", style="cyan")
            continue

        if line.startswith("#"):
            match = re.match(r'^(#{1,6})\s+(.*)$', line)
            if match:
                hashes, text = match.groups()
                level = len(hashes)
                styles = {
                    1: "bold magenta",
                    2: "bold cyan",
                    3: "bold green",
                    4: "bold yellow",
                    5: "bold red",
                    6: "bold dim"
                }
                result.append(line + "\n", style=styles.get(level, "bold"))
            else:
                result.append(line + "\n")
        elif line.startswith(">"):
            result.append(line + "\n", style="bold magenta")
        elif line.startswith("- ") or line.startswith("* "):
            result.append(line + "\n", style="bold yellow")
        elif re.match(r'^\d+\.\s+', line):
            result.append(line + "\n", style="bold yellow")
        elif line.strip() == "":
            result.append("\n")
        else:
            rendered = _parse_inline_line(line)
            result.append(rendered)
            result.append("\n")

    return result


def _parse_inline_line(text: str) -> Text:
    result = Text()
    pattern = r'(\*\*\*([^*]+)\*\*\*|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|~~([^-]+)~~)'

    last_end = 0
    for match in re.finditer(pattern, text):
        if match.start() > last_end:
            result.append(text[last_end:match.start()], style=None)

        full = match.group(0)
        if full.startswith('***') and full.endswith('***'):
            result.append(match.group(2), style="bold italic")
        elif full.startswith('**') and full.endswith('**'):
            result.append(match.group(3), style="bold")
        elif full.startswith('*') and full.endswith('*'):
            result.append(match.group(4), style="italic")
        elif full.startswith('`') and full.endswith('`'):
            result.append(match.group(5), style="bold cyan")
        elif full.startswith('['):
            link_text = match.group(6)
            link_url = match.group(7)
            result.append(link_text, style="underline blue")
            result.append(f" ({link_url})", style="dim")
        elif full.startswith('~~') and full.endswith('~~'):
            result.append(match.group(8), style="strike dim")

        last_end = match.end()

    if last_end < len(text):
        result.append(text[last_end:], style=None)

    if not result.plain:
        result.append(text, style=None)

    return result
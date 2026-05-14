# Markdown Rendering in CLI

## Overview

Automatically renders `.md` files in the CLI when they are written by the agent, instead of showing just a "file written" success message or diff output.

## Implementation Date

May 15, 2026

## Feature Detection

The feature auto-detects `.md` files by checking the file extension in `format_tool_output()`:

```python
if Path(path).suffix.lower() == ".md":
    render_markdown(path)
    continue
```

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Added `mistune` dependency |
| `src/liteagent/cli/markdown_renderer.py` | **New** - Markdown to Rich rendering |
| `src/liteagent/cli/formatter.py` | Added import and .md detection logic |

## Supported Markdown Elements

- **Headers** (H1-H6) - Styled with bold and color by level
- **Code blocks** (fenced with ```) - Displayed in cyan
- **Inline code** (`code`) - Bold cyan
- **Bold** (`**text**`) - Bold style
- **Italic** (`*text*`) - Italic style
- **Strikethrough** (`~~text~~`) - Strike dim style
- **Links** (`[text](url)`) - Underlined blue with URL in dim
- **Blockquotes** (`> text`) - Bold magenta
- **Lists** (- item or 1. item) - Bold yellow
- **Horizontal rules** (`---`) - Dim dashes
- **Paragraphs** - Regular text

## Rendering Behavior

- Files are rendered in a cyan-bordered Panel with the filename as title
- Files larger than 200 lines are truncated with a note
- Non-.md files continue to show diffs as before
- Empty files show a note instead of rendering

## Usage Example

When an agent writes a markdown file:

```
Agent: 🔧 Tool: write_file (README.md)

+-------- README.md --------+
| # My Project             |
|                          |
| ## Installation          |
|                          |
| Run: `npm install`       |
|                          |
| - Step 1                 |
| - Step 2                 |
+--------------------------+
```

## Dependencies

- `mistune` - Fast markdown parser (added to pyproject.toml)
- `rich` - Already used in the project for CLI output

## Alternative Approaches Considered

1. **Explicit flag in tool call** - Agent passes `render_as_markdown=True` - Rejected because it requires agent changes
2. **Separate tool** - New `render_markdown` tool - Rejected because it adds complexity
3. **Auto-detect .md files** - Chosen for seamless UX with no agent changes needed
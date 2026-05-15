## Commands Reference for Agents

### Setup Commands

| Command | Description |
|---------|-------------|
| `code-review-graph build` | Full build of knowledge graph |
| `code-review-graph update` | Incremental update (changed files only) |
| `code-review-graph status` | Show graph statistics |

---

### Query Commands

#### `query` - Query Graph Relationships

Find relationships between code elements.

```bash
# Find who calls a function
code-review-graph query callers_of <function_name> --format json

# Find what a function calls
code-review-graph query callees_of <function_name> --format json

# Find what a file imports
code-review-graph query imports_of <file_path> --format json

# Find who imports a file
code-review-graph query importers_of <file_path> --format json

# Find tests for a function/class
code-review-graph query tests_for <function_name> --format json

# Get summary of a file
code-review-graph query file_summary <file_path> --format json
```

**Example Agent Prompt:**
> "Find all callers of the `process_payment` function using: `code-review-graph query callers_of process_payment --format json`"

---

#### `search` - Semantic Search

Search for functions, classes, or files by name or keyword.

```bash
# Basic search
code-review-graph search "<query>" --format json

# Filter by kind (File, Class, Function, Type, Test)
code-review-graph search "<query>" --kind Function --format json

# Limit results
code-review-graph search "<query>" --limit 10 --format json
```

**Example Agent Prompt:**
> "Search for authentication-related code: `code-review-graph search authentication --format json`"

---

#### `traverse` - Graph Traversal

Walk the graph from a starting node.

```bash
# Traverse callees (what this function calls)
code-review-graph traverse <node_name> --direction callees --format json

# Traverse callers (who calls this function)
code-review-graph traverse <node_name> --direction callers --format json

# Control depth and size
code-review-graph traverse <node_name> --max-depth 3 --max-nodes 50 --format json
```

---

### Impact Analysis Commands

#### `impact` - Blast Radius Analysis

Find what's affected by changes.

```bash
# Auto-detect changed files from git
code-review-graph impact --format json

# Specify files manually
code-review-graph impact --files "src/auth.py,src/user.py" --format json

# Control depth
code-review-graph impact --depth 3 --format json
```

**Example Agent Prompt:**
> "Analyze the impact of changes in auth.py: `code-review-graph impact --files src/auth.py --format json`"

---

#### `affected-flows` - Execution Flow Analysis

Find which execution paths are affected by changes.

```bash
code-review-graph affected-flows --format json
code-review-graph affected-flows --files "src/auth.py" --format json
```

---

### Flow Commands

#### `flows` - List Execution Flows

List execution paths sorted by criticality.

```bash
# List top flows by criticality
code-review-graph flows --limit 20 --format json

# Sort by different criteria
code-review-graph flows --sort depth --format json
code-review-graph flows --sort node_count --format json

# Filter by entry point kind
code-review-graph flows --kind Test --format json
```

---

#### `flow` - Get Flow Details

Get details of a specific execution flow.

```bash
# By ID
code-review-graph flow 1 --format json

# By name (partial match)
code-review-graph flow "login" --format json

# Include source code
code-review-graph flow 1 --source --format json
```

---

### Community Commands

#### `communities` - List Code Communities

List detected code groups/modules.

```bash
code-review-graph communities --format json
code-review-graph communities --sort size --format table
```

---

#### `community` - Get Community Details

```bash
code-review-graph community "<name>" --format json
code-review-graph community "<name>" --members --format json
```

---

#### `architecture` - Architecture Overview

Get high-level architecture summary.

```bash
code-review-graph architecture --format markdown
```

---

### Analysis Commands

#### `hubs` - Architectural Hotspots

Find most connected nodes.

```bash
code-review-graph hubs --limit 20 --format json
```

---

#### `bridges` - Architectural Chokepoints

Find nodes that connect communities.

```bash
code-review-graph bridges --limit 20 --format json
```

---

#### `gaps` - Structural Weaknesses

Identify potential issues.

```bash
code-review-graph gaps --format json
```

---

#### `surprises` - Unexpected Coupling

Find surprising connections.

```bash
code-review-graph surprises --limit 20 --format json
```

---

#### `questions` - Review Questions

Auto-generated review questions.

```bash
code-review-graph questions --format json
```

---

### Refactoring Commands

#### `refactor` - Refactoring Tools

```bash
# Preview a rename
code-review-graph refactor rename <old_name> <new_name> --format json

# Find dead code
code-review-graph refactor dead-code --format json
code-review-graph refactor dead-code --kind Function --format json

# Get refactoring suggestions
code-review-graph refactor suggest --format json
```

---

#### `large-functions` - Find Large Code

Find oversized functions or classes.

```bash
code-review-graph large-functions --min-lines 50 --format json
code-review-graph large-functions --kind Class --min-lines 100 --format json
```

---

### Documentation Commands

#### `docs` - Get Documentation

```bash
code-review-graph docs usage
code-review-graph docs commands
code-review-graph docs troubleshooting
```

---

### Wiki Commands

#### `wiki` - Generate Wiki

Generate markdown documentation.

```bash
code-review-graph wiki
```

---

#### `wiki-page` - Get Wiki Page

```bash
code-review-graph wiki-page "<community_name>" --format markdown
```

---

## Output Formats

All commands support three output formats:

| Format | Flag | Use Case |
|--------|------|----------|
| JSON | `--format json` | Machine parsing, scripting |
| Table | `--format table` | Human reading in terminal |
| Markdown | `--format markdown` | Documentation, reports |

---

## Common Agent Workflows

### Workflow 1: Code Review Before Commit

```bash
# 1. Check current changes
code-review-graph status

# 2. Analyze impact
code-review-graph impact --format json

# 3. Check affected flows
code-review-graph affected-flows --format json

# 4. Get review questions
code-review-graph questions --format json
```

### Workflow 2: Understanding New Codebase

```bash
# 1. Build graph
code-review-graph build

# 2. Get architecture overview
code-review-graph architecture --format markdown

# 3. List communities
code-review-graph communities --format table

# 4. Find key hubs
code-review-graph hubs --limit 10 --format table
```

### Workflow 3: Refactoring Planning

```bash
# 1. Find large functions
code-review-graph large-functions --min-lines 50 --format json

# 2. Find dead code
code-review-graph refactor dead-code --format json

# 3. Get suggestions
code-review-graph refactor suggest --format json

# 4. Check impact of renaming
code-review-graph refactor rename OldName NewName --format json
```

### Workflow 4: Debugging

```bash
# 1. Search for related code
code-review-graph search "<error_keyword>" --format json

# 2. Trace execution
code-review-graph traverse "<function_name>" --direction callees --format json

# 3. Find callers
code-review-graph query callers_of "<function_name>" --format json

# 4. Check affected flows
code-review-graph affected-flows --files "<file_with_bug>" --format json
```

---

## Tips for Agents

1. **Always use `--format json`** for machine-readable output that can be parsed.

2. **Build the graph first** before running analysis commands.

3. **Use `status` command** to verify the graph is up to date.

4. **Combine commands** for comprehensive analysis:
   - `impact` + `affected-flows` for change analysis
   - `search` + `query` for code exploration
   - `hubs` + `bridges` for architecture understanding

5. **Parse JSON output** to extract specific information:
   ```python
   import json
   import subprocess
   
   result = subprocess.run(
       ["code-review-graph", "flows", "--limit", "10", "--format", "json"],
       capture_output=True,
       text=True
   )
   flows = json.loads(result.stdout)
   for flow in flows:
       print(flow["name"], flow["criticality"])
   ```

---

## Error Handling

If a command fails:

1. **Check if graph is built**: Run `code-review-graph status`
2. **Rebuild if needed**: Run `code-review-graph build`
3. **Check file paths**: Use relative paths from project root
4. **Verify dependencies**: Some commands require networkx

---

## Comparison: MCP vs CLI

| Feature | MCP Tools | CLI Wrappers |
|---------|-----------|--------------|
| Requires MCP support | Yes | No |
| Works with any agent | No | Yes |
| Output formats | JSON only | JSON, table, markdown |
| Interactive dialogue | Yes | No |
| Scripting friendly | No | Yes |
| Piping to other tools | No | Yes |

---

## Need Help?

```bash
# General help
code-review-graph --help

# Command-specific help
code-review-graph query --help
code-review-graph flows --help

# Documentation
code-review-graph docs usage
code-review-graph docs commands
```

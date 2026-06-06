from typing import List, Set, Dict, Optional
from .providers import ToolProviderFactory
import sqlite3
from pathlib import Path

def create_trace_method_workflows_tool(providers: ToolProviderFactory):
    def trace_method_workflows(target_name: str, direction: str = "both", max_depth: int = 2) -> str:
        """
        Takes a specific method or class name and returns its complete execution context, showing its upstream callers and downstream dependencies.
        
        Args:
            target_name: The exact name of the method or class to trace (e.g., StartAdvertising or DiscoveryService.StartAdvertising).
            direction: "upstream" (show callers), "downstream" (show callees), or "both". Defaults to "both".
            max_depth: How far up/down the call stack to trace. Defaults to 2.
        """
        try:
            db_path = Path(providers.project_dir) / ".liteagent" / "insight" / "knowledge.db"
            if not db_path.exists():
                return "Error: knowledge.db not found. Ensure the project is indexed."
                
            conn = sqlite3.connect(str(db_path))
            
            # Resolve target_name to qualified_names
            cursor = conn.execute("SELECT qualified_name, file_path, start_line FROM symbols WHERE name = ? OR qualified_name = ? OR name LIKE ?", 
                                  (target_name, target_name, f"%.{target_name}"))
            resolved = cursor.fetchall()
            
            if not resolved:
                return f"Could not find any symbol matching '{target_name}' in the database."
                
            output = [f"Tracing workflows for: {target_name}"]
            
            for qualified_name, file_path, start_line in resolved:
                output.append(f"\n--- Resolved target: {qualified_name} ({file_path}:{start_line}) ---")
                
                if direction in ["upstream", "both"]:
                    output.append("\n▼ UPSTREAM WORKFLOWS (How it gets called):")
                    
                    def build_upstream_tree(current_qn: str, depth: int, path_so_far: list) -> list:
                        if depth > int(max_depth) or current_qn in [x[0] for x in path_so_far]:
                            return []
                        
                        c = conn.execute("SELECT source, file_path FROM relationships WHERE target = ?", (current_qn,))
                        parents = c.fetchall()
                        
                        if not parents:
                            # Reached a root
                            return [path_so_far]
                            
                        all_paths = []
                        for parent_qn, p_file in parents:
                            pc = conn.execute("SELECT start_line FROM symbols WHERE qualified_name = ?", (parent_qn,))
                            p_line = pc.fetchone()
                            line_str = f":{p_line[0]}" if p_line else ""
                            
                            new_path = path_so_far + [(parent_qn, p_file, line_str, depth)]
                            sub_paths = build_upstream_tree(parent_qn, depth + 1, new_path)
                            if not sub_paths:
                                all_paths.append(new_path)
                            else:
                                all_paths.extend(sub_paths)
                        return all_paths
                        
                    paths = build_upstream_tree(qualified_name, 1, [])
                    if not paths:
                        output.append("  (No callers found)")
                    else:
                        for i, p in enumerate(paths):
                            output.append(f"\n  Flow {i+1}:")
                            p.reverse() 
                            for step in p:
                                sqn, sf, sl, sdepth = step
                                indent = "  " + "   " * (len(p) - sdepth)
                                prefix = "└── " if sdepth < len(p) else ""
                                output.append(f"  {indent}{prefix}[Depth {sdepth}] {sqn} ({sf}{sl})")
                            
                            t_indent = "  " + "   " * len(p)
                            output.append(f"  {t_indent}└── [TARGET] {qualified_name}")
                            
                if direction in ["downstream", "both"]:
                    output.append("\n▼ DOWNSTREAM DEPENDENCIES (What it calls):")
                    output.append(f"  [TARGET] {qualified_name}")
                    
                    visited_down = set()
                    
                    def print_downstream_tree(current_qn: str, depth: int):
                        if depth > int(max_depth) or current_qn in visited_down:
                            return
                        visited_down.add(current_qn)
                        
                        c = conn.execute("SELECT target, file_path FROM relationships WHERE source = ?", (current_qn,))
                        children = c.fetchall()
                        
                        for i, (child_qn, c_file) in enumerate(children):
                            prefix = "├── " if i < len(children) - 1 else "└── "
                            indent = "  " + "   " * depth
                            output.append(f"  {indent}{prefix}[Depth {depth}] {child_qn} ({c_file})")
                            print_downstream_tree(child_qn, depth + 1)
                            
                    print_downstream_tree(qualified_name, 1)
                    if len(visited_down) <= 1:
                        output.append("  (No downstream dependencies found)")
            
            conn.close()
            return "\n".join(output)
            
        except Exception as e:
            return f"Error tracing workflows: {str(e)}"
            
    return trace_method_workflows

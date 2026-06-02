import os
from pathlib import Path
import tree_sitter
import tree_sitter_c_sharp
from .graph_store import KnowledgeGraph

class ASTParser:
    """Tree-sitter based parser for C# files."""
    def __init__(self, graph_store: KnowledgeGraph, code_collection=None):
        self.graph_store = graph_store
        self.code_collection = code_collection
        self.parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_c_sharp.language()))
        
    def parse_directory(self, root_dir: Path):
        valid_exts = (".cs", ".csproj", ".sln", ".json", ".config", ".xml", ".cshtml", ".razor")
        ignore_dirs = {".git", "bin", "obj", "node_modules", ".venv", "__pycache__", ".liteagent", "models"}
        for path in root_dir.rglob("*"):
            try:
                rel_path = path.relative_to(root_dir)
                if any(part in ignore_dirs for part in rel_path.parts):
                    continue
            except ValueError:
                continue
                
            if path.is_file() and path.suffix in valid_exts:
                self.parse_file(path)
            
    def parse_file(self, file_path: Path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code_str = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return
            
        # Clean up existing references for this file to prevent stale data
        self.graph_store.clear_file(str(file_path))
        if self.code_collection:
            try:
                self.code_collection.delete(where={"file_path": str(file_path)})
            except Exception:
                pass
                
        # If it's not a C# file, just index the entire file text as a single "File" symbol
        if file_path.suffix != ".cs":
            qname = f"file.{file_path.name}"
            line_count = len(code_str.split('\n'))
            self.graph_store.insert_symbol(file_path.name, qname, "File", str(file_path), 1, line_count, code_str)
            if self.code_collection:
                self.code_collection.upsert(
                    ids=[qname], 
                    documents=[code_str], 
                    metadatas=[{
                        "name": file_path.name, 
                        "file_path": str(file_path),
                        "method_name": file_path.name # Use filename as method_name for non-cs files
                    }]
                )
            return
            
        tree = self.parser.parse(code_str.encode("utf8"))
        self._extract_symbols_and_relations(tree.root_node, code_str, str(file_path))
        
    def _split_with_overlap(self, text: str, chunk_size: int = 800, overlap: int = 200):
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start += chunk_size - overlap
        return chunks

    def _index_method_chunks(self, method_name, class_name, signature, source, file_path):
        if not self.code_collection:
            return
        chunks = self._split_with_overlap(source)
        for i, chunk in enumerate(chunks):
            # Prepend signature to every chunk so each embedding carries method context
            enriched = f"{signature}\n{chunk}"
            chunk_id = f"method.{method_name}::chunk_{i}::{file_path}"
            self.code_collection.upsert(
                ids=[chunk_id],
                documents=[enriched],
                metadatas=[{
                    "file_path": file_path,
                    "class_name": class_name or "",
                    "method_name": method_name,
                    "chunk_index": i
                }]
            )

    def _index_class_summary(self, class_name, method_signatures, file_path):
        if not self.code_collection:
            return
        summary = f"class {class_name}:\n" + "\n".join(method_signatures)
        chunk_id = f"class_summary.{class_name}::{file_path}"
        self.code_collection.upsert(
            ids=[chunk_id],
            documents=[summary],
            metadatas=[{
                "file_path": file_path,
                "class_name": class_name,
                "method_name": "",   # marks it as a class-level entry
                "chunk_index": -1
            }]
        )

    def _extract_symbols_and_relations(self, root_node, code_str, file_path):
        lines = code_str.split('\n')
        
        def get_identifier(node):
            name_node = node.child_by_field_name("name")
            if name_node:
                return code_str[name_node.start_byte:name_node.end_byte]
            for child in node.children:
                if child.type == "identifier":
                    return code_str[child.start_byte:child.end_byte]
            return None

        def get_method_signature(node):
            body_node = node.child_by_field_name("body")
            if body_node:
                return code_str[node.start_byte:body_node.start_byte].strip()
            return lines[node.start_point[0]].strip()
            
        current_class = None
        current_method = None
        
        def traverse(node):
            nonlocal current_class, current_method
            
            if node.type == "class_declaration":
                name = get_identifier(node)
                if name:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    source = "\n".join(lines[start_line-1:end_line])
                    qname = f"class.{name}"
                    self.graph_store.insert_symbol(name, qname, "Class", file_path, start_line, end_line, source)
                    
                    # Index class summary
                    if self.code_collection:
                        sigs = []
                        # Look for method children to build a "table of contents"
                        for child in node.children:
                            if child.type == "method_declaration":
                                sigs.append(get_method_signature(child))
                        self._index_class_summary(name, sigs, file_path)
                    
                    prev_class = current_class
                    current_class = name
                    for child in node.children:
                        traverse(child)
                    current_class = prev_class
                return
                    
            elif node.type == "method_declaration":
                name = get_identifier(node)
                if name:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    source = "\n".join(lines[start_line-1:end_line])
                    qname = f"method.{name}"
                    self.graph_store.insert_symbol(name, qname, "Function", file_path, start_line, end_line, source, current_class)
                    
                    if self.code_collection:
                        sig = get_method_signature(node)
                        self._index_method_chunks(name, current_class, sig, source, file_path)
                    
                    prev_method = current_method
                    current_method = name
                    for child in node.children:
                        traverse(child)
                    current_method = prev_method
                return
                
            elif node.type == "invocation_expression":
                if current_method:
                    callee_name = None
                    if len(node.children) > 0:
                        expr_node = node.children[0]
                        if expr_node.type == "identifier":
                            callee_name = code_str[expr_node.start_byte:expr_node.end_byte]
                        elif expr_node.type == "member_access_expression":
                            last_child = expr_node.children[-1]
                            if last_child.type == "identifier":
                                callee_name = code_str[last_child.start_byte:last_child.end_byte]
                    
                    if callee_name:
                        self.graph_store.insert_relationship(current_method, callee_name, "calls", file_path)
                        
                        # Extract log templates
                        lower_callee = callee_name.lower()
                        if "log" in lower_callee or "appendalltext" in lower_callee or "writeline" in lower_callee:
                            arg_node = node.child_by_field_name("arguments") or next((c for c in node.children if c.type == "argument_list"), None)
                            if arg_node:
                                arg_text = code_str[arg_node.start_byte:arg_node.end_byte]
                                import re
                                strings = re.findall(r'"([^"]*)"', arg_text)
                                for s in strings:
                                    if len(s) > 3:
                                        lvl = "INFO"
                                        if "error" in lower_callee or "[ERROR]" in s: lvl = "ERROR"
                                        elif "warn" in lower_callee or "[WARN]" in s: lvl = "WARN"
                                        elif "fatal" in lower_callee or "[FATAL]" in s: lvl = "FATAL"
                                        elif "debug" in lower_callee or "[DEBUG]" in s: lvl = "DEBUG"
                                        
                                        # Safely escape ALL regex characters
                                        # But first strip raw C# escape sequences like \n, \r
                                        s = s.replace('\\n', '').replace('\\r', '').replace('\\t', '')
                                        escaped_s = re.escape(s)
                                        # re.escape turns {var} into \{var\}. We replace it with non-greedy wildcard (.*?)
                                        template = re.sub(r'\\\{.*?\\\}', '(.*?)', escaped_s)
                                        
                                        self.graph_store.insert_log_template(file_path, current_method, lvl, template)
            
            for child in node.children:
                traverse(child)
                
        traverse(root_node)

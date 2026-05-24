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
        for path in root_dir.rglob("*"):
            if path.suffix in valid_exts:
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
                self.code_collection.upsert(ids=[qname], documents=[code_str], metadatas=[{"name": file_path.name, "file_path": str(file_path)}])
            return
            
        tree = self.parser.parse(code_str.encode("utf8"))
        self._extract_symbols_and_relations(tree.root_node, code_str, str(file_path))
        
    def _extract_symbols_and_relations(self, root_node, code_str, file_path):
        lines = code_str.split('\n')
        
        def get_identifier(node):
            for child in node.children:
                if child.type == "identifier":
                    return code_str[child.start_byte:child.end_byte]
            return None
            
        current_method = None
        
        def traverse(node):
            nonlocal current_method
            
            if node.type == "class_declaration":
                name = get_identifier(node)
                if name:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    source = "\n".join(lines[start_line-1:end_line])
                    qname = f"class.{name}"
                    self.graph_store.insert_symbol(name, qname, "Class", file_path, start_line, end_line, source)
                    if self.code_collection:
                        self.code_collection.upsert(ids=[qname], documents=[source], metadatas=[{"name": name, "file_path": file_path}])
                    
            elif node.type == "method_declaration":
                name = get_identifier(node)
                if name:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    source = "\n".join(lines[start_line-1:end_line])
                    qname = f"method.{name}"
                    self.graph_store.insert_symbol(name, qname, "Function", file_path, start_line, end_line, source)
                    if self.code_collection:
                        self.code_collection.upsert(ids=[qname], documents=[source], metadatas=[{"name": name, "file_path": file_path}])
                    
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
                            for c in expr_node.children:
                                if c.type == "identifier" and c != expr_node.children[0]:
                                    callee_name = code_str[c.start_byte:c.end_byte]
                    
                    if callee_name:
                        self.graph_store.insert_relationship(current_method, callee_name, "calls", file_path)
            
            for child in node.children:
                traverse(child)
                
        traverse(root_node)

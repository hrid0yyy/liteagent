import json
from pathlib import Path
from typing import Optional

def setup_insight_tools(project_dir: Path):
    """
    Initializes the Insight Engine and returns the tools for the LangGraph agent.
    """
    # Create necessary directories
    insight_dir = project_dir / ".liteagent" / "insight"
    insight_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize components here (e.g., GraphStore, VectorStore, LogIndex)
    from .indexer.graph_store import KnowledgeGraph
    from .indexer.ast_parser import ASTParser
    from .logs.log_index import LogIndex
    from .logs.analyzer import LogAnalyzer
    from .retrieval.retriever import HybridRetriever
    
    import chromadb
    
    # Try to load heavy ML models, but gracefully fallback to a Dummy function if it fails 
    # due to missing dependencies, MemoryErrors, or testing flags, so the SQLite tools still work!
    try:
        import os
        if os.environ.get("LITEAGENT_TESTING") == "1":
            raise Exception("Testing mode enabled, skipping ML.")
        from chromadb.utils import embedding_functions
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    except Exception as e:
        print(f"[WARN] ML Model skipped ({str(e)}). Semantic Search will be mocked.")
        class DummyEmbeddingFunction:
            def __call__(self, input):
                return [[0.0] * 384 for _ in input]
            def name(self) -> str:
                return "sentence_transformer"
        emb_fn = DummyEmbeddingFunction()

    chroma_client = chromadb.PersistentClient(path=str(insight_dir / "chromadb"))
    code_collection = chroma_client.get_or_create_collection("code_symbols", embedding_function=emb_fn)

    graph_store = KnowledgeGraph(insight_dir / "knowledge.db")
    ast_parser = ASTParser(graph_store, code_collection)
    ast_parser.parse_directory(project_dir)
    
    # --- File System Watcher ---
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class CodeChangeHandler(FileSystemEventHandler):
            valid_exts = (".cs", ".csproj", ".sln", ".json", ".config", ".xml", ".cshtml", ".razor")
            
            def on_modified(self, event):
                if event.is_directory: return
                if event.src_path.endswith(self.valid_exts):
                    ast_parser.parse_file(Path(event.src_path))
                    
            def on_created(self, event):
                if event.is_directory: return
                if event.src_path.endswith(self.valid_exts):
                    ast_parser.parse_file(Path(event.src_path))

        observer = Observer()
        observer.schedule(CodeChangeHandler(), str(project_dir), recursive=True)
        observer.start()
        # Thread will run in the background (daemon)
    except ImportError:
        pass
        
    log_index = LogIndex(insight_dir / "log_index.db")
    log_analyzer = LogAnalyzer(log_index)
    retriever = HybridRetriever(insight_dir, code_collection)

    def search_code(query: str, top_k: int = 8) -> str:
        """
        Performs a hybrid vector + BM25 keyword search across the codebase.
        Ideal for finding logic without knowing exact file names.
        """
        try:
            results = retriever.search(query, top_k)
            if not results:
                return f"No code found matching: {query}"
            
            output = []
            for r in results:
                output.append(f"File: {r['file_path']}\nSymbol: {r.get('symbol_name', 'Unknown')}\nCode:\n{r['source_code']}\n---")
            return "\n".join(output)
        except Exception as e:
            return f"Error searching code: {str(e)}"

    def trace_calls(symbol: str, direction: str = "both", depth: int = 3, max_nodes: int = 50) -> str:
        """
        Traverses the AST call graph.
        'callers' shows what relies on or uses the symbol.
        'callees' shows what the symbol uses.
        """
        try:
            results = graph_store.trace_calls(symbol, direction, depth, max_nodes)
            return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error tracing calls: {str(e)}"

    def search_logs(query: str, is_plain: bool = True, context_lines: int = 2, level: Optional[str] = None, last_hours: Optional[int] = None, error_code: Optional[str] = None, limit: int = 50) -> str:
        """
        Queries the FTS5 log index.
        Use is_plain=True for instant keyword/error code lookup.
        Use is_plain=False for Python Regex directly against raw log lines.
        context_lines controls how many lines before and after the match are returned.
        """
        try:
            results = log_index.search(query, is_plain, context_lines, level, last_hours, error_code, limit)
            if not results:
                return f"No logs found matching query: {query}"
            
            output = []
            for r in results:
                output.append(f"[{r.get('timestamp', 'UNKNOWN')}] {r.get('level', 'INFO')} - Line {r.get('line_number', '?')} - {r.get('file_path', 'unknown')}\nContext:\n{r.get('context', '')}\n---")
            return "\n".join(output)
        except Exception as e:
            return f"Error searching logs: {str(e)}"

    def get_log_stats(module: str = None, level: str = None, last_hours: int = 24) -> str:
        """
        The Universal Log Profiler.
        Queries AST extracted log templates and calculates their occurrence stats from the log file.
        Use module to filter by file or class name, and level (e.g. ERROR) to filter by severity.
        """
        try:
            templates = graph_store.get_log_templates(module, level)
            if not templates:
                return f"No log templates found in codebase for module={module}, level={level}."
                
            stats = {}
            for t in templates:
                query = t["template"]
                results = log_index.search(query, is_plain=False, limit=10000)
                
                if results:
                    stats[query] = {
                        "count": len(results),
                        "level": t["level"],
                        "file": Path(t["file_path"]).name,
                        "method": t["method_name"]
                    }
                
            if not stats:
                return f"All {len(templates)} extracted log templates returned 0 occurrences. System healthy."
                
            output = [f"Log Statistics for module={module}, level={level}:"]
            for template, data in stats.items():
                output.append(f"- [{data['level']}] {template} -> Found in: {data['file']}::{data['method']} | Occurrences: {data['count']}")
            return "\n".join(output)
        except Exception as e:
            return f"Error getting log stats: {str(e)}"

    def trace_log_to_code(log_string: str) -> str:
        """
        Cross-references an exact log string with AST-extracted templates to find
        exactly which file and method generated it.
        """
        try:
            templates = graph_store.get_log_templates()
            import re
            
            matched_template = None
            for t in templates:
                pattern = t["template"]
                try:
                    if re.search(pattern, log_string):
                        matched_template = t
                        break
                except re.error:
                    continue
                    
            if not matched_template:
                return "This log does not match any extracted templates from the codebase. It may originate from a third-party dependency or the AST index is outdated."
                
            cursor = graph_store.conn.cursor()
            cursor.execute("SELECT start_line, end_line, source_code FROM symbols WHERE file_path COLLATE NOCASE = ? AND name = ?", 
                          (matched_template["file_path"], matched_template["method_name"]))
            row = cursor.fetchone()
            
            output = [
                f"Log successfully traced!",
                f"File: {matched_template['file_path']}",
                f"Method: {matched_template['method_name']}",
                f"Level: {matched_template['level']}"
            ]
            
            if row:
                output.append(f"Line: {row[0]}-{row[1]}")
                output.append(f"Source Code:\n{row[2]}")
            else:
                output.append("Source code snippet could not be retrieved.")
                
            return "\n".join(output)
        except Exception as e:
            return f"Error tracing log to code: {str(e)}"

    return [search_code, trace_calls, search_logs, get_log_stats, trace_log_to_code]

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
    from chromadb.utils import embedding_functions

    chroma_client = chromadb.PersistentClient(path=str(insight_dir / "chromadb"))
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
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

    def get_project_map(path: str = ".") -> str:
        """
        Returns a depth-1 folder/module overview.
        Use this to understand directory structures progressively.
        """
        try:
            target_path = project_dir / path
            if not target_path.exists():
                return f"Path does not exist: {target_path}"
            if not target_path.is_dir():
                return f"Not a directory: {target_path}"
            
            items = []
            for item in target_path.iterdir():
                kind = "DIR " if item.is_dir() else "FILE"
                items.append(f"[{kind}] {item.name}")
            return "\n".join(sorted(items))
        except Exception as e:
            return f"Error reading project map: {str(e)}"

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

    def get_log_errors(path: str = "auto", last_hours: int = 24, include_stats: bool = True) -> str:
        """
        Groups and de-duplicates all recent [ERROR] or [FATAL] logs.
        Returns aggregate statistics to prevent context overflow.
        """
        try:
            summary = log_analyzer.get_recent_errors(path, last_hours, include_stats)
            return json.dumps(summary, indent=2)
        except Exception as e:
            return f"Error getting log errors: {str(e)}"

    def trace_error_to_code(error_string: str) -> str:
        """
        Cross-references an error string from logs to find exactly which function threw the error.
        Returns the full execution context, file path, and line number.
        """
        try:
            result = log_analyzer.trace_error_to_code(error_string, graph_store)
            if not result:
                return f"Could not map error to source code: {error_string}"
            return result
        except Exception as e:
            return f"Error tracing error to code: {str(e)}"

    return [search_code, trace_calls, get_project_map, search_logs, get_log_errors, trace_error_to_code]

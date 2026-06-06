from pathlib import Path
import threading
from .indexer.graph_store import KnowledgeGraph
from .indexer.ast_parser import ASTParser
from .logs.log_index import LogIndex
from .retrieval.retriever import HybridRetriever

class InsightProviders:
    def __init__(self, project_dir: Path):
        insight_dir = project_dir / ".liteagent" / "insight"
        insight_dir.mkdir(parents=True, exist_ok=True)
        
        import os
        
        self.graph_store = KnowledgeGraph(insight_dir / "knowledge.db")
        self.ast_parser = ASTParser(self.graph_store)
        
        # Parse directory
        if os.environ.get("LITEAGENT_SYNC_INDEXING") == "1" or os.environ.get("LITEAGENT_TESTING") == "1":
            self.ast_parser.parse_directory(project_dir)
        else:
            threading.Thread(target=self.ast_parser.parse_directory, args=(project_dir,), daemon=True).start()
        
        # Mutable container so the watchdog closure can update the retriever reference
        _retriever_holder = [None]

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            ast_parser = self.ast_parser

            class CodeChangeHandler(FileSystemEventHandler):
                valid_exts = (".cs", ".csproj", ".sln", ".json", ".config", ".xml", ".cshtml", ".razor")
                ignore_dirs = {".git", ".vs", "bin", "obj", "node_modules", ".venv", "__pycache__", ".liteagent", "models", "packages"}
                
                def _is_valid(self, path_str: str) -> bool:
                    p = Path(path_str)
                    if not p.suffix in self.valid_exts: return False
                    if any(part in self.ignore_dirs for part in p.parts): return False
                    return True

                def on_modified(self, event):
                    if event.is_directory: return
                    if self._is_valid(event.src_path):
                        ast_parser.parse_file(Path(event.src_path))
                        if _retriever_holder[0]:
                            _retriever_holder[0].mark_stale()
                        
                def on_created(self, event):
                    if event.is_directory: return
                    if self._is_valid(event.src_path):
                        ast_parser.parse_file(Path(event.src_path))
                        if _retriever_holder[0]:
                            _retriever_holder[0].mark_stale()

            observer = Observer()
            observer.schedule(CodeChangeHandler(), str(project_dir), recursive=True)
            observer.start()
        except ImportError:
            pass

        self.log_index = LogIndex(project_dir)
        self.retriever = HybridRetriever(insight_dir)
        
        # Wire up retriever reference for watchdog stale marking
        _retriever_holder[0] = self.retriever

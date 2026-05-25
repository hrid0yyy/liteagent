from pathlib import Path
from .indexer.graph_store import KnowledgeGraph
from .indexer.ast_parser import ASTParser
from .logs.log_index import LogIndex
from .logs.analyzer import LogAnalyzer
from .retrieval.retriever import HybridRetriever

class InsightProviders:
    def __init__(self, project_dir: Path):
        insight_dir = project_dir / ".liteagent" / "insight"
        insight_dir.mkdir(parents=True, exist_ok=True)
        
        import chromadb
        import os
        
        try:
            if os.environ.get("LITEAGENT_TESTING") == "1":
                raise Exception("Testing mode enabled, skipping ML.")
            from chromadb.utils import embedding_functions
            emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[WARN] ML Model skipped ({str(e)}). Semantic Search will be mocked.")
            from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
            class DummyEmbeddingFunction(EmbeddingFunction):
                def __call__(self, input: Documents) -> Embeddings:
                    return [[0.0] * 384 for _ in input]
                def name(self) -> str:
                    return "sentence_transformer"
            emb_fn = DummyEmbeddingFunction()

        chroma_client = chromadb.PersistentClient(path=str(insight_dir / "chromadb"))
        self.code_collection = chroma_client.get_or_create_collection("code_symbols", embedding_function=emb_fn)

        self.graph_store = KnowledgeGraph(insight_dir / "knowledge.db")
        self.ast_parser = ASTParser(self.graph_store, self.code_collection)
        self.ast_parser.parse_directory(project_dir)
        
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            ast_parser = self.ast_parser

            class CodeChangeHandler(FileSystemEventHandler):
                valid_exts = (".cs", ".csproj", ".sln", ".json", ".config", ".xml", ".cshtml", ".razor")
                ignore_dirs = {".git", "bin", "obj", "node_modules", ".venv", "__pycache__", ".liteagent"}
                
                def _is_valid(self, path_str: str) -> bool:
                    p = Path(path_str)
                    if not p.suffix in self.valid_exts: return False
                    if any(part in self.ignore_dirs for part in p.parts): return False
                    return True

                def on_modified(self, event):
                    if event.is_directory: return
                    if self._is_valid(event.src_path):
                        ast_parser.parse_file(Path(event.src_path))
                        
                def on_created(self, event):
                    if event.is_directory: return
                    if self._is_valid(event.src_path):
                        ast_parser.parse_file(Path(event.src_path))

            observer = Observer()
            observer.schedule(CodeChangeHandler(), str(project_dir), recursive=True)
            observer.start()
        except ImportError:
            pass

        self.log_index = LogIndex(insight_dir / "log_index.db")
        self.log_analyzer = LogAnalyzer(self.log_index)
        self.retriever = HybridRetriever(insight_dir, self.code_collection)

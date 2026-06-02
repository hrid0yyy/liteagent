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
        
        import chromadb
        import os
        
        try:
            if os.environ.get("LITEAGENT_TESTING") == "1":
                raise Exception("Testing mode enabled, skipping ML.")
            
            embed_model = os.environ.get("LITEAGENT_EMBED_MODEL", "minilm").lower()
            local_model_path = None
            if embed_model == "nomic":
                model_name = "nomic-ai/nomic-embed-text-v1.5"
            elif embed_model == "bge":
                model_name = "BAAI/bge-m3"
            else:
                # Check for local model in project dir, then in package dir
                local_model_path = project_dir / "models" / "all-MiniLM-L6-v2"
                if not local_model_path.exists():
                    pkg_model_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / "all-MiniLM-L6-v2"
                    if pkg_model_path.exists():
                        local_model_path = pkg_model_path
                
                if local_model_path.exists():
                    model_name = str(local_model_path)
                else:
                    model_name = "all-MiniLM-L6-v2"

            # Use SentenceTransformer directly instead of chromadb's wrapper
            # This gives us full control over local_files_only and avoids
            # chromadb's own import check that produces confusing error messages
            from sentence_transformers import SentenceTransformer
            from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
            
            local_only = local_model_path is not None and local_model_path.exists()
            st_model = SentenceTransformer(model_name, local_files_only=local_only)
            
            class LocalSentenceTransformerFn(EmbeddingFunction):
                def __init__(self, model):
                    self._model = model
                def __call__(self, input: Documents) -> Embeddings:
                    return self._model.encode(input).tolist()
                def name(self) -> str:
                    return "sentence_transformer"
            
            emb_fn = LocalSentenceTransformerFn(st_model)
            print("[INFO] Semantic Search enabled (local model loaded).")
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
        
        # Parse directory
        if os.environ.get("LITEAGENT_SYNC_INDEXING") == "1" or os.environ.get("LITEAGENT_TESTING") == "1":
            self.ast_parser.parse_directory(project_dir)
        else:
            threading.Thread(target=self.ast_parser.parse_directory, args=(project_dir,), daemon=True).start()
        
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
        self.retriever = HybridRetriever(insight_dir, self.code_collection)

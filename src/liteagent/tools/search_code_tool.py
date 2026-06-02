from .providers import ToolProviderFactory

def create_search_code_tool(providers: ToolProviderFactory):
    def search_code(query: str, top_k: int = 3) -> str:
        """
        Searches the codebase for specific functionality, concepts, or logic.
        Use this when you need to find code but don't know the exact file names.
        Returns the file path, symbol name, and source code snippet.
        
        Args:
            query: The search query, concept, or logic to look for.
            top_k: The maximum number of results to return (default: 3).
        """
        try:
            top_k = int(top_k) if top_k not in (None, "") else 3
            results = providers.insight.retriever.search(query, top_k)
            if not results:
                return f"No code found matching: {query}"
            
            output = []
            for r in results:
                header = f"File: {r['file_path']}"
                if r.get("class_name"):
                    header += f"\nClass: {r['class_name']}"
                header += f"\nSymbol: {r.get('symbol_name', 'Unknown')}"
                if r.get("context_note"):
                    header += f"\n[Context: {r['context_note']}]"
                output.append(f"{header}\nCode:\n{r['source_code']}\n---")
            return "\n".join(output)
        except Exception as e:
            return f"Error searching code: {str(e)}"
    return search_code

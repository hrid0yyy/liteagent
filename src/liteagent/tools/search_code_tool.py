from .providers import ToolProviderFactory

def create_search_code_tool(providers: ToolProviderFactory):
    def search_code(query: str, top_k: int = 8) -> str:
        """
        Searches the codebase for specific functionality, concepts, or logic.
        Use this when you need to find code but don't know the exact file names.
        Returns the file path, symbol name, and source code snippet.
        
        Args:
            query: The search query, concept, or logic to look for.
            top_k: The maximum number of results to return (default: 8).
        """
        try:
            results = providers.insight.retriever.search(query, top_k)
            if not results:
                return f"No code found matching: {query}"
            
            output = []
            for r in results:
                output.append(f"File: {r['file_path']}\nSymbol: {r.get('symbol_name', 'Unknown')}\nCode:\n{r['source_code']}\n---")
            return "\n".join(output)
        except Exception as e:
            return f"Error searching code: {str(e)}"
    return search_code

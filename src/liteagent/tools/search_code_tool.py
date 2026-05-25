from .providers import ToolProviderFactory

def create_search_code_tool(providers: ToolProviderFactory):
    def search_code(query: str, top_k: int = 8) -> str:
        """
        Performs a hybrid vector + BM25 keyword search across the codebase.
        Ideal for finding logic without knowing exact file names.
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

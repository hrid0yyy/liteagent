from .providers import ToolProviderFactory

MAX_TOP_K = 5
DEFAULT_TOP_K = 2

def create_search_code_tool(providers: ToolProviderFactory):
    def search_code(query: str, top_k: int = DEFAULT_TOP_K) -> str:
        """
        Searches the codebase for classes, methods, or functions by name or keyword.
        Use class or method names as queries for best results.
        Results where the query matches a class/method name are ranked first.
        Returns the file path, class name, and source code snippet.
        
        Args:
            query: Class name, method name, or space-separated keywords to search for.
            top_k: Maximum number of results to return. Default is 2, maximum is 5.
        """

        try:
            top_k = int(top_k) if top_k not in (None, "") else DEFAULT_TOP_K
            if top_k < 1:
                top_k = 1
            if top_k > MAX_TOP_K:
                top_k = MAX_TOP_K
            results = providers.insight.retriever.search(query, top_k)
            if not results:
                return f"No code found matching: {query}"
            
            output = []
            for r in results:
                header = f"File: {r['file_path']}"
                if r.get("class_name"):
                    header += f"\nClass: {r['class_name']}"
                output.append(f"{header}\nCode:\n{r['source_code']}\n---")
            return "\n".join(output)
        except Exception as e:
            return f"Error searching code: {str(e)}"
    return search_code

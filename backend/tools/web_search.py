import time
from typing import List
from langchain_core.tools import tool
from tavily import TavilyClient

class ToolError(Exception):
    """Custom exception for tool failures."""
    pass

@tool
def web_search(query: str, max_results: int = 5) -> List[dict]:
    """Search the web for information using the Tavily API.
    
    Args:
        query: The search query.
        max_results: The maximum number of results to return.
        
    Returns:
        List of dictionaries containing url, title, content, and score.
    """
    from backend.config.settings import settings
    
    if not settings.TAVILY_API_KEY:
        raise ToolError("TAVILY_API_KEY is missing. Please set it in your environment.")
        
    try:
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    except Exception as e:
        raise ToolError(f"Failed to initialize TavilyClient: {e}") from e
    
    retries = 3
    delays = [1, 2, 4]
    
    for attempt in range(retries):
        try:
            response = client.search(query=query, max_results=max_results, search_depth="advanced")
            results = []
            for result in response.get("results", []):
                results.append({
                    "url": result.get("url"),
                    "title": result.get("title"),
                    "content": result.get("content"),
                    "score": result.get("score")
                })
            return results
        except Exception as e:
            if attempt == retries - 1:
                raise ToolError(f"Web search failed after {retries} attempts: {e}") from e
            time.sleep(delays[attempt])
    return []

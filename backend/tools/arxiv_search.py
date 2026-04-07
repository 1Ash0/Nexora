import datetime
from typing import List
from langchain_core.tools import tool
import arxiv

@tool
def arxiv_search(query: str, max_results: int = 5) -> List[dict]:
    """Search the ArXiv pre-print repository for academic papers.
    
    Args:
        query: The search query (e.g., "transformer architecture").
        max_results: The maximum number of results to return.
        
    Returns:
        List of dictionaries containing paper details.
    """
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results * 2, # Fetch more to allow filtering
        sort_by=arxiv.SortCriterion.Relevance
    )
    
    results = []
    current_year = datetime.datetime.now().year
    
    for result in client.results(search):
        # Filter: only papers from the last 5 years
        if result.published.year >= current_year - 5:
            results.append({
                "arxiv_id": result.get_short_id(),
                "title": result.title,
                "authors": [author.name for author in result.authors],
                "abstract": result.summary,
                "pdf_url": result.pdf_url,
                "published": result.published.isoformat()
            })
            
            if len(results) >= max_results:
                break
                
    return results

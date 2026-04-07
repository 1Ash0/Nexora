import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

@tool
def load_url(url: str) -> str:
    """Fetch and extract main text content from a web page URL.
    
    Args:
        url: The web page URL to load.
        
    Returns:
        Extracted text content from the first 3 chunks (approx 1500 tokens).
    """
    try:
        # Fetch the URL with a 10s timeout
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return f"Error: Cannot extract text from non-HTML content type: {content_type}"
                
            html = response.text
            
    except httpx.TimeoutException:
        return f"Error: Timeout after 10s while fetching URL: {url}"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} while fetching URL: {url}"
    except Exception as e:
        return f"Error: Failed to fetch URL: {e}"

    # Parse HTML and strip nav/footer/ads
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove unwanted elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        element.decompose()
        
    # Get text
    text = soup.get_text(separator="\n")
    
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    # Chunk into 500-token segments
    try:
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=500, chunk_overlap=0
        )
        splits = text_splitter.split_text(text)
    except ImportError:
        # Fallback to character based splitting if tiktoken is not installed
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000, chunk_overlap=0
        )
        splits = text_splitter.split_text(text)
        
    # Return joined text of first 3 chunks
    return "\n\n".join(splits[:3])

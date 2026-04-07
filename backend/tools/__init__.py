from backend.tools.web_search import web_search
from backend.tools.arxiv_search import arxiv_search
from backend.tools.document_loader import load_url

EXECUTOR_TOOLS = [web_search, arxiv_search, load_url]

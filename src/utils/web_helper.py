import os
import requests
import base64
from typing import List, Optional
from pydantic import BaseModel
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
from duckduckgo_search import DDGS
import arxiv

load_dotenv()


class WebSearchResult(BaseModel):
    title: str
    url: str
    description: str
    
class WebBrowseResult(BaseModel):
    title: str | None = None
    url: str
    content: str
    error: str | None = None

class GitHubRepoResult(BaseModel):
    name: str
    full_name: str
    description: str | None = None
    url: str
    stars: int
    language: str | None = None
    readme_content: str | None = None
    error: str | None = None


# Initialize Firecrawl app
_firecrawl_app = None

def _get_firecrawl_app():
    """Get or create Firecrawl app instance."""
    global _firecrawl_app
    if _firecrawl_app is None:
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            raise ValueError("FIRECRAWL_API_KEY not found in environment variables")
        _firecrawl_app = FirecrawlApp(api_key=api_key)
    return _firecrawl_app


def web_search(query: str, limit: int = 3) -> List[WebSearchResult]:
    """
    Search the web for information on a given topic.
    
    Args:
        query: Search query describing what you're looking for
        limit: Maximum number of results to return (default: 3, max: 5)

    Returns:
        List of WebSearchResult objects with title, URL, and description
    """
    try:
        print(f"Using Firecrawl search for: {query}")
        app = _get_firecrawl_app()
        
        # Use Firecrawl's search capability for better results
        search_result = app.search(query, limit=limit)
        
        results = []
        # Access results via .data attribute
        if hasattr(search_result, 'data') and search_result.data:
            for result in search_result.data:
                results.append(WebSearchResult(
                    title=result.get('title', ''),
                    url=result.get('url', ''),
                    description=result.get('description', '')
                ))
        
        # If no results from Firecrawl, try DuckDuckGo fallback
        if not results:
            results = _get_fallback_results(query, limit)

        return results
        
    except Exception as e:
        print(f"Firecrawl search error: {e}")
        # Return SerpAPI fallback results
        return _get_fallback_results(query, limit)


def _get_fallback_results(query: str, limit: int = 3) -> List[WebSearchResult]:
    """
    Provide fallback results using DuckDuckGo search when Firecrawl fails.
    """
    print(f"Using DuckDuckGo fallback search for: {query}")
    results = []
    try:
        with DDGS() as ddgs:
            ddgs_results = list(ddgs.text(query, max_results=limit))
            for result in ddgs_results:
                results.append(WebSearchResult(
                    title=result.get('title', ''),
                    url=result.get('href', ''),
                    description=result.get('body', '')
                ))
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
    return results
    

def search_arxiv(query: str, limit: int = 3) -> List[WebSearchResult]:
    """
    Search arxiv for papers.
    
    Args:
        query: Search query for arxiv
        limit: Maximum number of results to return (default: 3)

    Returns:
        List of WebSearchResult objects with arxiv paper information
    """
    try:
        print(f"Using Arxiv search for: {query}")
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance
        )
        results = []
        for r in search.results():
            results.append(WebSearchResult(
                title=r.title,
                url=r.pdf_url,
                description=r.summary
            ))
        return results
    except Exception as e:
        print(f"Arxiv search error: {e}")
        return []


def search_github(query: str, limit: int = 5) -> List[WebSearchResult]:
    """
    Search GitHub repositories specifically.
    
    Args:
        query: Search query for GitHub repositories
        limit: Maximum number of results to return (default: 5, max: 10)

    Returns:
        List of WebSearchResult objects with GitHub repository information
    """
    try:
        print(f"Using GitHub search for: {query}")
        github_query = f"site:github.com {query}"
        results = web_search(github_query, limit)
        
        # If no results from web search, try GitHub-specific fallbacks
        if not results:
            results = _get_github_fallbacks(query, limit)
            
        return results
        
    except Exception as e:
        return _get_github_fallbacks(query, limit)


def _get_github_fallbacks(query: str, limit: int = 5) -> List[WebSearchResult]:
    """
    Provide GitHub-specific fallback results using DuckDuckGo site search.
    """
    print(f"Using GitHub fallback search for: {query}")
    github_query = f"site:github.com {query}"
    return _get_fallback_results(github_query, limit)


def get_github_repo_info(repo_url: str) -> GitHubRepoResult:
    """
    Get repository information and README content from GitHub API.
    
    Args:
        repo_url: GitHub repository URL (e.g., 'https://github.com/owner/repo')
        
    Returns:
        GitHubRepoResult with repository information and README content
    """
    try:
        # Extract owner and repo name from URL
        if 'github.com' not in repo_url:
            return GitHubRepoResult(
                name="", full_name="", url=repo_url, stars=0,
                error="Invalid GitHub URL"
            )
        
        # Parse URL to get owner/repo
        parts = repo_url.replace('https://github.com/', '').replace('http://github.com/', '').split('/')
        if len(parts) < 2:
            return GitHubRepoResult(
                name="", full_name="", url=repo_url, stars=0,
                error="Invalid GitHub repository URL format"
            )
        
        owner, repo = parts[0], parts[1]
        
        # GitHub API headers
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'prisma-Web-Agent'
        }
        
        # Add GitHub token if available
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        # Get repository information
        repo_api_url = f'https://api.github.com/repos/{owner}/{repo}'
        repo_response = requests.get(repo_api_url, headers=headers)
        
        if repo_response.status_code != 200:
            return GitHubRepoResult(
                name=repo, full_name=f"{owner}/{repo}", url=repo_url, stars=0,
                error=f"Failed to fetch repository info: {repo_response.status_code}"
            )
        
        repo_data = repo_response.json()
        
        # Get README content
        readme_content = None
        readme_api_url = f'https://api.github.com/repos/{owner}/{repo}/readme'
        readme_response = requests.get(readme_api_url, headers=headers)
        
        if readme_response.status_code == 200:
            readme_data = readme_response.json()
            # Decode base64 content
            readme_content = base64.b64decode(readme_data['content']).decode('utf-8')
            
            # Limit content length
            if len(readme_content) > 8000:
                readme_content = readme_content[:8000] + "...\n[README truncated]"
        
        return GitHubRepoResult(
            name=repo_data.get('name', ''),
            full_name=repo_data.get('full_name', ''),
            description=repo_data.get('description', ''),
            url=repo_data.get('html_url', repo_url),
            stars=repo_data.get('stargazers_count', 0),
            language=repo_data.get('language', ''),
            readme_content=readme_content
        )
        
    except Exception as e:
        return GitHubRepoResult(
            name="", full_name="", url=repo_url, stars=0,
            error=f"Error fetching GitHub repository: {str(e)}"
        )


def browse_url(url: str) -> WebBrowseResult:
    """
    Browse and extract content from a URL using Firecrawl.
    
    Args:
        url: URL to browse and extract content from
        
    Returns:
        WebBrowseResult with extracted content or error information
    """
    try:
        app = _get_firecrawl_app()
        
        # Use Firecrawl's scrape capability with correct v1 API format
        scrape_result = app.scrape_url(url, formats=['markdown', 'html'], only_main_content=True)
        
        # Handle ScrapeResponse object format
        if hasattr(scrape_result, 'data'):
            data = scrape_result.data
            content = data.get('markdown', '') or data.get('content', '') or data.get('html', '')
            metadata = data.get('metadata', {})
            title = metadata.get('title', '') if metadata else ''
        else:
            # Fallback for direct attribute access
            content = getattr(scrape_result, 'markdown', '') or getattr(scrape_result, 'content', '') or getattr(scrape_result, 'html', '')
            metadata = getattr(scrape_result, 'metadata', {})
            title = metadata.get('title', '') if metadata else ''
        
        # Limit content length
        if len(content) > 5000:
            content = content[:5000] + "...\n[Content truncated]"
        
        return WebBrowseResult(
            title=title,
            url=url,
            content=content
        )
        
    except Exception as e:
        return WebBrowseResult(
            title=None,
            url=url,
            content="",
            error=f"Failed to browse URL with Firecrawl: {str(e)}"
        )


if __name__ == "__main__":
    results = web_search("Python data visualization libraries", limit=2)
    print(results)
    
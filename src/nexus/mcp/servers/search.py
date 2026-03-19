"""Web search MCP server for NEXUS using Tavily."""

import os
from fastmcp import FastMCP

search_server = FastMCP("NEXUS Web Search")


@search_server.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information using Tavily."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not set. Web search is unavailable."

    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        if not results:
            return f"No results found for: {query}"

        lines = [f"Search results for '{query}':\n"]
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. {result.get('title', 'No title')}")
            lines.append(f"   URL: {result.get('url', '')}")
            lines.append(f"   {result.get('content', '')[:200]}\n")

        return "\n".join(lines)

    except Exception as e:
        return f"Error performing web search: {str(e)}"

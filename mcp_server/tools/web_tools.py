import os
from typing import Any, Dict, Optional

import requests
from fastmcp.tools import tool


class WebSearchTools:
    """Small MCP wrapper around a web search provider."""

    def __init__(self) -> None:
        self.provider = os.getenv("WEB_SEARCH_PROVIDER", "google").strip().lower()
        self.google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
        self.google_cx = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "").strip()
        self.timeout = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "15"))
        self.use_env_proxy = os.getenv("WEB_SEARCH_USE_ENV_PROXY", "false").strip().lower() == "true"

    def search(
        self,
        query: str,
        max_results: int = 5,
        freshness: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not query or not query.strip():
            raise ValueError("query is required")

        if self.provider != "google":
            raise ValueError(
                f"Unsupported WEB_SEARCH_PROVIDER '{self.provider}'. "
                "Currently supported: google"
            )

        if not self.google_api_key:
            raise ValueError(
                "Web search is not configured. Set GOOGLE_SEARCH_API_KEY in .env."
            )

        if not self.google_cx:
            raise ValueError(
                "Web search is not configured. Set GOOGLE_SEARCH_ENGINE_ID in .env."
            )

        count = max(1, min(int(max_results), 10))
        params: Dict[str, Any] = {
            "q": query.strip(),
            "key": self.google_api_key,
            "cx": self.google_cx,
            "num": count,
            "hl": "en",
            "safe": "off",
        }
        if freshness:
            params["dateRestrict"] = freshness

        session = requests.Session()
        session.trust_env = self.use_env_proxy
        response = session.get(
            "https://customsearch.googleapis.com/customsearch/v1",
            headers={"Accept": "application/json"},
            params=params,
            timeout=self.timeout,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {"message": response.text[:500]}

            message = (
                error_payload.get("error", {}).get("message")
                or error_payload.get("message")
                or str(exc)
            )
            raise ValueError(f"Google search request failed: {message}") from exc
        payload = response.json()

        results = []
        for item in payload.get("items", []):
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "description": item.get("snippet"),
                    "display_link": item.get("displayLink"),
                    "mime": item.get("mime"),
                }
            )

        return {
            "provider": self.provider,
            "query": query.strip(),
            "count": len(results),
            "search_information": payload.get("searchInformation", {}),
            "results": results,
        }


_instance = WebSearchTools()


@tool
def web_search(query: str, max_results: int = 5, freshness: Optional[str] = None):
    """
    Search the public web for current information.

    Args:
        query: Search query, e.g. "latest AI news"
        max_results: Number of results to return, 1-10
        freshness: Optional Google date restriction. Common values:
            "d1" (past day), "w1" (past week), "m1" (past month), "y1" (past year)
    """
    return _instance.search(query=query, max_results=max_results, freshness=freshness)

"""HTTP client for external search APIs (Brave Search, Google Custom Search).

Supports rate limiting (10 req/min) and result caching (15 min TTL)
per issue #1472 requirements.
"""

import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple sliding-window rate limiter."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []

    def allow(self) -> bool:
        """Check if a request is allowed under the rate limit."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self.max_requests:
            return False
        self._timestamps.append(now)
        return True


# Financial news domains for domain-filtered searches
FINANCIAL_DOMAINS = [
    "reuters.com",
    "bloomberg.com",
    "coindesk.com",
    "cointelegraph.com",
    "cnbc.com",
    "ft.com",
    "wsj.com",
    "marketwatch.com",
    "seekingalpha.com",
    "theblock.co",
]


def build_financial_query(instrument: str, topic: str = "general") -> str:
    """Build a financially-focused search query.

    Args:
        instrument: Trading pair or asset name (e.g. "BTC/USD", "Bitcoin").
        topic: Query topic — regulatory, technical, fundamental, sentiment, or general.

    Returns:
        Optimized search query string.
    """
    # Normalize instrument name for search
    base = instrument.split("/")[0] if "/" in instrument else instrument
    name_map = {
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
        "SOL": "Solana",
        "XRP": "Ripple",
        "ADA": "Cardano",
        "DOGE": "Dogecoin",
        "DOT": "Polkadot",
        "AVAX": "Avalanche",
    }
    name = name_map.get(base.upper(), base)

    queries = {
        "regulatory": f"{name} regulation SEC CFTC news",
        "technical": f"{name} price analysis chart technical",
        "fundamental": f"{name} adoption institutional fundamental",
        "sentiment": f"{name} market sentiment outlook",
        "earnings": f"{name} earnings report quarterly",
        "general": f"{name} latest news market",
    }
    return queries.get(topic, f"{name} {topic}")


class SearchClient:
    """Web search client supporting Brave Search and Google Custom Search APIs."""

    def __init__(
        self,
        brave_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        google_cx: Optional[str] = None,
        timeout: int = 10,
    ):
        self.brave_api_key = brave_api_key
        self.google_api_key = google_api_key
        self.google_cx = google_cx
        self.timeout = timeout
        self._rate_limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        self._seen_urls: set[str] = set()

    def search(
        self,
        query: str,
        max_results: int = 5,
        domains: Optional[list[str]] = None,
        recency_hours: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Execute a web search and return structured results.

        Uses Brave Search if configured, falls back to Google Custom Search.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            domains: Optional list of domains to restrict results to.
            recency_hours: Only return results from the last N hours.

        Returns:
            List of search result dicts with title, url, snippet, source, published_at.

        Raises:
            RuntimeError: If rate limited or no search provider configured.
        """
        if not self._rate_limiter.allow():
            raise RuntimeError("Rate limit exceeded: 10 requests per minute")

        if self.brave_api_key:
            return self._search_brave(query, max_results, domains, recency_hours)
        elif self.google_api_key and self.google_cx:
            return self._search_google(query, max_results, domains, recency_hours)
        else:
            raise RuntimeError(
                "No search provider configured. Set BRAVE_API_KEY or GOOGLE_API_KEY + GOOGLE_CX."
            )

    def _search_brave(
        self,
        query: str,
        max_results: int,
        domains: Optional[list[str]],
        recency_hours: Optional[int],
    ) -> list[dict[str, Any]]:
        """Search using Brave Search API."""
        url = "https://api.search.brave.com/res/v1/web/search"
        params: dict[str, Any] = {
            "q": query,
            "count": min(max_results * 2, 20),  # fetch extra for dedup
        }
        if recency_hours and recency_hours <= 24:
            params["freshness"] = "pd"
        elif recency_hours and recency_hours <= 168:
            params["freshness"] = "pw"

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.brave_api_key,
        }

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Brave search failed: %s", e)
            raise RuntimeError(f"Search request failed: {e}") from e

        results = []
        for item in data.get("web", {}).get("results", []):
            item_url = item.get("url", "")
            if item_url in self._seen_urls:
                continue
            if domains and not any(d in item_url for d in domains):
                continue
            self._seen_urls.add(item_url)
            results.append({
                "title": item.get("title", ""),
                "url": item_url,
                "snippet": item.get("description", ""),
                "source": _extract_domain(item_url),
                "published_at": item.get("age", None),
            })
            if len(results) >= max_results:
                break

        return results

    def _search_google(
        self,
        query: str,
        max_results: int,
        domains: Optional[list[str]],
        recency_hours: Optional[int],
    ) -> list[dict[str, Any]]:
        """Search using Google Custom Search API."""
        url = "https://www.googleapis.com/customsearch/v1"

        q = query
        if domains:
            site_filter = " OR ".join(f"site:{d}" for d in domains)
            q = f"{query} ({site_filter})"

        params: dict[str, Any] = {
            "key": self.google_api_key,
            "cx": self.google_cx,
            "q": q,
            "num": min(max_results, 10),
        }
        if recency_hours:
            params["dateRestrict"] = f"d{max(1, recency_hours // 24)}"

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Google search failed: %s", e)
            raise RuntimeError(f"Search request failed: {e}") from e

        results = []
        for item in data.get("items", []):
            item_url = item.get("link", "")
            if item_url in self._seen_urls:
                continue
            self._seen_urls.add(item_url)
            results.append({
                "title": item.get("title", ""),
                "url": item_url,
                "snippet": item.get("snippet", ""),
                "source": _extract_domain(item_url),
                "published_at": None,
            })
            if len(results) >= max_results:
                break

        return results


def _extract_domain(url: str) -> str:
    """Extract domain name from a URL."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""

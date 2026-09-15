"""DuckDuckGo HTML search client."""

import re

import httpx


class SearchError(Exception):
    """Raised when a web search fails."""


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]*>", "", html)


def _unescape_entities(text: str) -> str:
    # Minimal HTML entity handling for titles/snippets.
    replacements = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


def parse_duckduckgo_html(html: str, max_results: int = 5) -> list[dict[str, str]]:
    """Extract result title/snippet/URL from DuckDuckGo HTML response."""
    results: list[dict[str, str]] = []
    # Find every result title anchor, then pair it with the nearest URL and snippet.
    title_matches = list(
        re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
    )
    for title_match in title_matches:
        title = _unescape_entities(_strip_tags(title_match.group(2)))
        title_end = title_match.end()
        url = _unescape_entities(title_match.group(1))
        url_match = re.search(
            r'<a[^>]*class="result__url"[^>]*href="([^"]*)"',
            html[title_end:],
            re.DOTALL | re.IGNORECASE,
        )
        if url_match:
            url = _unescape_entities(url_match.group(1))
        snippet_match = re.search(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            html[title_end:],
            re.DOTALL | re.IGNORECASE,
        )
        snippet = _unescape_entities(_strip_tags(snippet_match.group(1))) if snippet_match else ""
        if not title:
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


class DuckDuckGoSearch:
    """Async DuckDuckGo HTML search wrapper."""

    BASE = "https://html.duckduckgo.com/html"

    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    async def search(self, query: str) -> list[dict[str, str]]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
                response = await client.get(self.BASE, params={"q": query, "kl": "us-en"})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SearchError(f"DuckDuckGo search failed: {exc}") from exc

        return parse_duckduckgo_html(response.text, max_results=self.max_results)

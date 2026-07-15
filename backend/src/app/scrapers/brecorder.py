"""Business Recorder news scraper.

Pulls the latest markets/business news from brecorder.com. The public site
sometimes blocks scrapers, so every call is best-effort — empty list on
failure. Provides a ``_tag_tickers`` helper that heuristically maps uppercase
PSX tickers from the headline/body text.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, application/xhtml+xml;q=0.9, */*;q=0.5",
}

# News + markets feeds (RSS first, then HTML).
NEWS_URLS = [
    "https://www.brecorder.com/markets",
    "https://markets.brecorder.com/",
    "https://www.brecorder.com/business",
]


class BRecorderScraper:
    """Scrapes brecorder.com/markets for the latest PSX-relevant headlines."""

    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(2)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                headers=GET_HEADERS,
                timeout=15.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _try_fetch(self, urls: list[str]) -> str:
        last_exc: Exception | None = None
        for url in urls:
            try:
                client = await self._get_client()
                async with self._sem:
                    r = await client.get(url)
                    r.raise_for_status()
                    return r.text
            except Exception as e:  # noqa: BLE001
                last_exc = e
                continue
        log.warning("brecorder_unreachable", urls=urls, err=str(last_exc) if last_exc else None)
        return ""

    async def fetch_news(self, limit: int = 30) -> list[dict]:
        try:
            html = await self._try_fetch(NEWS_URLS)
            if not html:
                return []
            result = _parse_news_html(html, source="brecorder", limit=limit)
            if not result:
                log.warning("brecorder:empty_parse_200_html", url=NEWS_URLS[0] if NEWS_URLS else "")
            return result
        except Exception:
            log.warning("brecorder_fetch_failed", exc_info=True)
            return []

    @staticmethod
    def _tag_tickers(headline: str, body: str, known_symbols: set[str]) -> list[str]:
        """Find uppercase PSX tickers mentioned in the text.

        Heuristic: scan tokens matching the 2-5-char uppercase pattern and
        intersect with ``known_symbols``. Returned list is de-duplicated and
        in the same order as the first appearance.
        """
        text = f"{headline or ''} {body or ''}"
        tokens = re.findall(r"\b[A-Z]{2,5}\b", text)
        seen: set[str] = set()
        out: list[str] = []
        for tok in tokens:
            if tok in known_symbols and tok not in seen:
                seen.add(tok)
                out.append(tok)
        return out


# ---------- parsers ----------


_DATE_PATTERNS = (
    "%b %d, %Y %I:%M %p",
    "%B %d, %Y %I:%M %p",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d-%b-%Y",
)


def _parse_dt(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _abs_url(href: str, base: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith("javascript:") or href.startswith("#") or href.startswith("mailto:"):
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        # brecorder.com — use the marketing host.
        return f"https://www.brecorder.com{href}"
    return f"{base.rstrip('/')}/{href.lstrip('/')}"


def _parse_news_html(html: str, source: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []
    seen_urls: set[str] = set()
    base = "https://www.brecorder.com"

    # The BRecorder front pages render an <article> with a headline link for
    # every story. We also accept older <li class="story"> and generic <h2>/<h3>
    # blocks that wrap an <a>.
    candidates: list[tuple[str, str, str]] = []
    for art in soup.find_all("article"):
        a = art.find("a", href=True)
        if not a:
            continue
        headline = a.get_text(" ", strip=True)
        url = _abs_url(a["href"], base)
        ts_raw = ""
        time_tag = art.find("time")
        if time_tag:
            ts_raw = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        candidates.append((headline, url or "", ts_raw))
    for h in soup.find_all(["h2", "h3"]):
        a = h.find("a", href=True)
        if not a:
            continue
        headline = a.get_text(" ", strip=True)
        url = _abs_url(a["href"], base)
        if not url:
            continue
        ts_raw = ""
        parent = h.parent
        if parent:
            t = parent.find("time")
            if t:
                ts_raw = t.get("datetime") or t.get_text(" ", strip=True)
        candidates.append((headline, url, ts_raw))

    for headline, url, ts_raw in candidates:
        if not headline:
            continue
        if not url or not url.startswith("https://"):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        published = _parse_dt(ts_raw) if ts_raw else None
        items.append({
            "headline": headline,
            "url": url,
            "source": source,
            "published_at": published,
        })
        if len(items) >= limit:
            break
    return items

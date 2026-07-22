"""Business Recorder news scraper.

Reads brecorder's RSS feeds, not the HTML pages: as of 2026-07-16 every HTML
page (/markets, /business, markets.brecorder.com) returns **403** to any
client, including one sending a real Chrome User-Agent — it is bot protection,
not a header problem, so there is nothing to spoof our way past. The
/feeds/* endpoints serve the same stories as RSS 2.0 and are not blocked.

That also fixes a second, quieter bug: the HTML parser only ever produced a
headline and a URL, so psx_news.body and .summary were ALWAYS null and
``_tag_tickers`` had nothing but the headline to match against. RSS
``<description>`` carries the article text, so both now populate.

Every call stays best-effort — empty list on failure.
"""
from __future__ import annotations

import asyncio
import re
from email.utils import parsedate_to_datetime
from typing import Optional
from xml.etree import ElementTree as ET

import httpx
import structlog
from bs4 import BeautifulSoup

from app.scrapers._http import ResilientHTTP

log = structlog.get_logger()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5",
}

# RSS feeds, in preference order — markets first (most PSX-relevant), then
# progressively broader. First one that parses wins.
NEWS_URLS = [
    "https://www.brecorder.com/feeds/markets",
    "https://www.brecorder.com/feeds/business-finance",
    "https://www.brecorder.com/feeds/latest-news",
]

# content:encoded, when present, holds the full article; description holds a
# lead paragraph. Namespace per the RSS content module.
_CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


class BRecorderScraper:
    """Scrapes brecorder.com/markets for the latest PSX-relevant headlines."""

    def __init__(self) -> None:
        # Shared resilient client — retries the full TransportError family with
        # backoff. This scraper had no retry at all before (audit §7).
        self._http = ResilientHTTP(headers=GET_HEADERS, concurrency=2, name="brecorder")

    async def close(self) -> None:
        await self._http.aclose()

    async def _try_fetch(self, urls: list[str]) -> str:
        last_exc: Exception | None = None
        for url in urls:
            try:
                return await self._http.get_text(url)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                continue
        log.warning("brecorder_unreachable", urls=urls, err=str(last_exc) if last_exc else None)
        return ""

    async def fetch_news(self, limit: int = 30) -> list[dict]:
        try:
            xml = await self._try_fetch(NEWS_URLS)
            if not xml:
                return []
            result = _parse_news_rss(xml, source="brecorder", limit=limit)
            if not result:
                log.warning("brecorder:empty_parse_200_feed", url=NEWS_URLS[0])
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


def _text(html_or_text: str) -> str:
    """RSS descriptions are HTML fragments; psx_news stores plain text."""
    if not html_or_text:
        return ""
    return BeautifulSoup(html_or_text, "lxml").get_text(" ", strip=True)


def _parse_dt(raw: str) -> Optional[str]:
    """RSS pubDate is RFC 2822 ("Thu, 16 Jul 2026 12:26:48 +0500")."""
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw.strip()).isoformat()
    except (TypeError, ValueError):
        return None


def _parse_news_rss(xml: str, source: str, limit: int) -> list[dict]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        log.warning("brecorder:feed_not_xml")
        return []

    items: list[dict] = []
    seen_urls: set[str] = set()
    for it in root.findall(".//item"):
        headline = (it.findtext("title") or "").strip()
        url = (it.findtext("link") or "").strip()
        if not headline or not url.startswith("https://") or url in seen_urls:
            continue
        seen_urls.add(url)

        # Prefer whichever carries more of the article.
        description = it.findtext("description") or ""
        encoded = it.findtext(_CONTENT_NS) or ""
        body = _text(encoded if len(encoded) > len(description) else description)

        items.append({
            "headline": headline,
            "url": url,
            "source": source,
            "published_at": _parse_dt(it.findtext("pubDate") or ""),
            "body": body or None,
            # First paragraph-ish. The column exists for list views that should
            # not ship the whole article.
            "summary": (body[:300] + "…") if len(body) > 300 else (body or None),
        })
        if len(items) >= limit:
            break
    return items

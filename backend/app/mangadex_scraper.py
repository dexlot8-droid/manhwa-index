"""
MangaDex scraper using the Keiyoushi extension approach.
Searches MangaDex for series, fetches chapters, and extracts image URLs.

MangaDex API:
- Search: GET /manga?title=...&includes[]=cover_art
- Feed: GET /manga/{id}/feed?translatedLanguage[]=en
- At-home: GET /at-home/server/{chapterId} → page file list
- Images: https://uploads.mangadex.org/data/{hash}/{file}
"""

import asyncio
import re
import logging
from urllib.parse import urlparse
import httpx
from selectolax.parser import HTMLParser
from .config import SCRAPE_DELAY, USER_AGENT

logger = logging.getLogger(__name__)

MANGADEX_BASE = "https://api.mangadex.org"
MANGADEX_UPLOADS = "https://uploads.mangadex.org"


class MangaDexScraper:
    """Scraper for MangaDex (used by Keiyoushi extensions)."""

    name = "mangadex"
    BASE = "https://mangadex.org"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._last_request = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=30,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _get(self, url: str) -> dict:
        """GET JSON with rate limiting."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < SCRAPE_DELAY:
            await asyncio.sleep(SCRAPE_DELAY - elapsed)

        client = await self._get_client()
        resp = await client.get(url)
        self._last_request = asyncio.get_event_loop().time()

        if resp.status_code != 200:
            logger.warning(f"HTTP {resp.status_code} for {url}")
            return {}
        return resp.json()

    async def search_series(self, title: str) -> list[dict]:
        """Search for a series by title on MangaDex."""
        url = f"{MANGADEX_BASE}/manga?title={title}&limit=5&includes[]=cover_art"
        data = await self._get(url)

        if data.get("result") != "ok":
            return []

        results = []
        for m in data.get("data", []):
            attrs = m.get("attributes", {})
            titles = attrs.get("title", {})
            cover = m.get("relationships", [{}])[0] if m.get("relationships") else {}

            results.append({
                "id": m.get("id"),
                "title": titles.get("en", titles.get("ja-ro", "Unknown")),
                "description": attrs.get("description", {}).get("en", ""),
                "status": attrs.get("status", "unknown"),
                "year": attrs.get("year"),
                "cover_url": f"https://mangadex.org/covers/{m.get('id')}/{cover.get('attributes', {}).get('fileName', '')}" if cover else "",
            })

        return results

    async def get_series(self, url: str) -> dict:
        """Get series metadata from MangaDex URL or search."""
        # Extract manga ID from URL if provided
        match = re.search(r'/title/([a-f0-9-]+)', url)
        if match:
            manga_id = match.group(1)
            data = await self._get(f"{MANGADEX_BASE}/manga/{manga_id}?includes[]=cover_art")
            if data.get("result") == "ok":
                m = data["data"]
                attrs = m.get("attributes", {})
                titles = attrs.get("title", {})
                cover = m.get("relationships", [{}])[0] if m.get("relationships") else {}
                return {
                    "title": titles.get("en", titles.get("ja-ro", "Unknown")),
                    "cover_url": f"https://mangadex.org/covers/{m.get('id')}/{cover.get('attributes', {}).get('fileName', '')}" if cover else "",
                    "description": attrs.get("description", {}).get("en", ""),
                    "author": attrs.get("author", ["Unknown"])[0] if attrs.get("author") else "Unknown",
                    "status": attrs.get("status", "unknown"),
                    "tags": [t.get("attributes", {}).get("name", {}).get("en", "") for t in attrs.get("tags", [])],
                }

        # Search by title
        title = url.split("/")[-1].replace("-", " ").title()
        results = await self.search_series(title)
        if results:
            r = results[0]
            return {
                "title": r["title"],
                "cover_url": r["cover_url"],
                "description": r["description"],
                "author": r.get("author", "Unknown"),
                "status": r["status"],
                "tags": r.get("tags", []),
            }

        return {}

    async def get_chapters(self, url: str) -> list[dict]:
        """Get all chapters for a series from MangaDex."""
        # Extract manga ID
        match = re.search(r'/title/([a-f0-9-]+)', url)
        if not match:
            # Search for the series first
            title = url.split("/")[-1].replace("-", " ").title()
            results = await self.search_series(title)
            if not results:
                return []
            manga_id = results[0]["id"]
        else:
            manga_id = match.group(1)

        # Get chapter feed
        chapters = []
        offset = 0
        limit = 100

        while True:
            feed_url = f"{MANGADEX_BASE}/manga/{manga_id}/feed?translatedLanguage[]=en&limit={limit}&offset={offset}&order[chapter]=asc"
            data = await self._get(feed_url)

            if data.get("result") != "ok":
                break

            items = data.get("data", [])
            if not items:
                break

            for ch in items:
                attrs = ch.get("attributes", {})
                ch_num = attrs.get("chapter", "0")
                try:
                    ch_num = float(ch_num)
                except (ValueError, TypeError):
                    ch_num = 0

                chapters.append({
                    "chapter_number": ch_num,
                    "title": attrs.get("title", f"Chapter {ch_num}"),
                    "source_url": f"https://mangadex.org/chapter/{ch.get('id')}",
                    "image_urls": [],  # Will be populated by get_chapter_images
                })

            offset += limit
            if offset >= data.get("total", 0):
                break

        return chapters

    async def get_chapter_images(self, chapter_id: str) -> list[str]:
        """Get image URLs for a chapter using the at-home server."""
        # Get at-home server info
        server_url = f"{MANGADEX_BASE}/at-home/server/{chapter_id}"
        data = await self._get(server_url)

        if data.get("result") != "ok":
            return []

        base_url = data.get("baseUrl", "")
        chapter = data.get("chapter", {})
        hash_val = chapter.get("hash", "")
        pages = chapter.get("data", [])

        if not hash_val or not pages:
            return []

        # Build image URLs using uploads.mangadex.org (more reliable than at-home baseUrl)
        image_urls = []
        for page in pages:
            img_url = f"{MANGADEX_UPLOADS}/data/{hash_val}/{page}"
            image_urls.append(img_url)

        return image_urls

    async def scrape_full(self, title: str) -> dict:
        """Full scrape: search, get metadata, get chapters, get images."""
        # Search for series
        results = await self.search_series(title)
        if not results:
            return {"success": False, "error": "Series not found on MangaDex"}

        series = results[0]
        manga_id = series["id"]

        # Get chapters
        chapters = await self.get_chapters(f"https://mangadex.org/title/{manga_id}")

        # Get images for each chapter (limit to first 10 for speed)
        for ch in chapters[:10]:
            ch_id = ch["source_url"].split("/")[-1]
            images = await self.get_chapter_images(ch_id)
            ch["image_urls"] = images

        return {
            "success": True,
            "series": {
                "title": series["title"],
                "cover_url": series["cover_url"],
                "description": series["description"],
                "author": series.get("author", "Unknown"),
                "status": series["status"],
                "tags": series.get("tags", []),
            },
            "chapters": chapters,
            "source": "mangadex",
        }

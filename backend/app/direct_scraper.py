"""
Direct scraper for manhwa series using known CDN sources.
Bypasses MangaDex — uses abyssrift CDN and reference sites directly.
"""

import asyncio
import re
import logging
import httpx
from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

# Known CDN codes from reference sites (verified working)
CDN_CODES = {
    "nano-machine": "Nano",
    "star-embracing-swordmaster": "SES",
    "pick-me-up-infinite-gacha": "Gacha",
}

# Reference sites to scrape for series data
REFERENCE_SITES = {
    "nano-machine": "https://w72.readnanomachine.com/",
    "star-embracing-swordmaster": "https://star-embracingswordmaster.com/",
    "pick-me-up-infinite-gacha": "https://pickmeupgacha.com/",
    "myst-might-mayhem": "https://myst-might-mayhem.com/",
    "regressing-knight": "https://regressingknight.com/",
    "100regression": "https://100regression.com/",
    "swordhound": "https://swordhound.com/",
}


class DirectScraper:
    """Scrape manhwa data directly from reference sites and CDN."""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                follow_redirects=True,
                timeout=30,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, url: str) -> str:
        client = await self._get_client()
        resp = await client.get(url)
        if resp.status_code != 200:
            return ""
        return resp.text

    async def get_series_from_site(self, site_url: str) -> dict:
        """Scrape series metadata from a reference site."""
        html = await self._get(site_url)
        if not html:
            return {}

        tree = HTMLParser(html)

        # Try to find series title
        title = ""
        title_elem = tree.css_first("h1, .site-title, .logo-text, .brand-name")
        if title_elem:
            title = title_elem.text(strip=True)

        # Try to find cover image
        cover_url = ""
        cover_elem = tree.css_first(".site-logo img, .brand-logo img, .header-image img, .cover img")
        if cover_elem:
            cover_url = cover_elem.attributes.get("src", "")

        # Try to find description
        description = ""
        desc_elem = tree.css_first(".site-description, .about-text, .tagline")
        if desc_elem:
            description = desc_elem.text(strip=True)[:500]

        return {
            "title": title,
            "cover_url": cover_url,
            "description": description,
        }

    async def get_chapters_from_site(self, site_url: str, max_chapters: int = 100) -> list:
        """Scrape chapter list from a reference site."""
        html = await self._get(site_url)
        if not html:
            return []

        tree = HTMLParser(html)
        chapters = []

        # Find chapter links
        chapter_links = tree.css("a[href*='chapter'], a[href*='/ch']")

        for link in chapter_links[:max_chapters]:
            href = link.attributes.get("href", "")
            title_text = link.text(strip=True)

            if not href:
                continue

            # Extract chapter number
            match = re.search(r'chapter[-/]?(\d+(?:\.\d+)?)', href, re.I)
            if match:
                ch_num = float(match.group(1))
                chapters.append({
                    "chapter_number": ch_num,
                    "title": title_text or f"Chapter {ch_num}",
                    "source_url": href,
                    "image_urls": [],
                })

        return chapters

    async def get_cdn_chapters(self, code: str, max_chapters: int = 330) -> list:
        """Generate chapter URLs from CDN pattern."""
        chapters = []
        for ch in range(1, max_chapters + 1):
            # Try different URL patterns
            urls = [
                f"https://abyssrift.com/{code}/{ch}/01.webp",
                f"https://abyssrift.com/{code}/{ch:02d}/01.webp",
            ]
            chapters.append({
                "chapter_number": ch,
                "title": f"Chapter {ch}",
                "source_url": f"https://abyssrift.com/{code}/{ch}/",
                "image_urls": urls,
            })
        return chapters

    async def verify_cdn_chapter(self, code: str, chapter: int) -> bool:
        """Verify if a CDN chapter exists."""
        urls = [
            f"https://abyssrift.com/{code}/{chapter}/01.webp",
            f"https://abyssrift.com/{code}/{chapter:02d}/01.webp",
        ]
        client = await self._get_client()
        for url in urls:
            try:
                resp = await client.head(url, timeout=10)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
        return False

    async def scrape_series(self, slug: str, title: str) -> dict:
        """Scrape a series using all available methods."""
        # Method 1: Use known CDN code
        if slug in CDN_CODES:
            code = CDN_CODES[slug]
            chapters = await self.get_cdn_chapters(code)
            return {
                "success": True,
                "series": {
                    "title": title,
                    "cover_url": f"https://abyssrift.com/{code}/cover.webp",
                    "description": f"Read {title} online for free.",
                    "author": "Unknown",
                    "status": "ongoing",
                    "tags": ["action", "martial-arts", "fantasy"],
                },
                "chapters": chapters,
                "source": "abyssrift",
            }

        # Method 2: Scrape from reference site
        if slug in REFERENCE_SITES:
            site_url = REFERENCE_SITES[slug]
            series_data = await self.get_series_from_site(site_url)
            chapters = await self.get_chapters_from_site(site_url)

            if chapters:
                return {
                    "success": True,
                    "series": {
                        "title": series_data.get("title", title),
                        "cover_url": series_data.get("cover_url", ""),
                        "description": series_data.get("description", f"Read {title} online for free."),
                        "author": "Unknown",
                        "status": "ongoing",
                        "tags": ["action", "martial-arts", "fantasy"],
                    },
                    "chapters": chapters,
                    "source": "reference-site",
                }

        # Method 3: Try MangaDex as fallback
        return {"success": False, "error": "No source available"}

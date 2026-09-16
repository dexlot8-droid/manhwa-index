"""
Manhwa site scrapers.

Each scraper must implement:
- name: str (source site identifier)
- BASE: str (base URL)
- extract_slug(url: str) -> str: extract series slug from URL
- get_series(url: str) -> dict: scrape series metadata
- get_chapters(url: str) -> list[dict]: scrape chapter list with image URLs
"""

import asyncio
import re
import logging
from abc import ABC, abstractmethod
from urllib.parse import urlparse
import httpx
from selectolax.parser import HTMLParser
from .config import SCRAPE_DELAY, USER_AGENT

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all manhwa site scrapers."""

    name: str = ""
    BASE: str = ""

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

    async def _get(self, url: str) -> str:
        """GET with rate limiting."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < SCRAPE_DELAY:
            await asyncio.sleep(SCRAPE_DELAY - elapsed)

        client = await self._get_client()
        resp = await client.get(url)
        self._last_request = asyncio.get_event_loop().time()

        if resp.status_code != 200:
            logger.warning(f"HTTP {resp.status_code} for {url}")
            return ""
        return resp.text

    @abstractmethod
    def extract_slug(self, url: str) -> str:
        """Extract a URL-friendly slug from the series URL."""
        ...

    @abstractmethod
    async def get_series(self, url: str) -> dict:
        """Scrape series metadata. Returns dict with title, cover_url, description, etc."""
        ...

    @abstractmethod
    async def get_chapters(self, url: str) -> list[dict]:
        """Scrape all chapters. Returns list of dicts with chapter_number, title, source_url, image_urls."""
        ...


class AsuraScraper(BaseScraper):
    """Scraper for Asura Scans (asuratoon.com)."""

    name = "asura"
    BASE = "https://asuratoon.com"

    def extract_slug(self, url: str) -> str:
        # URL format: https://asuratoon.com/manga/solo-leveling/
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1]

    async def get_series(self, url: str) -> dict:
        html = await self._get(url)
        if not html:
            return {}

        tree = HTMLParser(html)

        # Try to extract metadata from the page
        title = ""
        cover_url = ""
        description = ""
        author = ""
        tags = []
        status = "ongoing"

        # Title
        title_elem = tree.css_first(".entry-title")
        if title_elem:
            title = title_elem.text(strip=True)

        # Cover
        cover_elem = tree.css_first(".thumb img")
        if cover_elem:
            cover_url = cover_elem.attributes.get("src", "")

        # Description
        desc_elem = tree.css_first(".entry-content p")
        if desc_elem:
            description = desc_elem.text(strip=True)[:500]

        # Author
        author_elem = tree.css_first(".author")
        if author_elem:
            author = author_elem.text(strip=True)

        # Status
        status_elem = tree.css_first(".status")
        if status_elem:
            status = status_elem.text(strip=True).lower()

        # Tags
        for tag in tree.css(".genre a"):
            tag_text = tag.text(strip=True).lower()
            if tag_text:
                tags.append(tag_text)

        return {
            "title": title,
            "cover_url": cover_url,
            "description": description,
            "author": author,
            "status": status,
            "tags": tags,
        }

    async def get_chapters(self, url: str) -> list[dict]:
        html = await self._get(url)
        if not html:
            return []

        tree = HTMLParser(html)
        chapters = []

        # Find chapter list - Asura uses various formats
        chapter_links = tree.css(".eplister a, .chapternum a, .chbox a, a[href*='/chapter']")

        for link in chapter_links:
            href = link.attributes.get("href", "")
            title_text = link.text(strip=True)

            if not href:
                continue

            # Extract chapter number from URL or text
            ch_num = self._extract_chapter_number(href, title_text)
            if ch_num is None:
                continue

            # Scrape the chapter page for image URLs
            image_urls = await self._get_chapter_images(href)

            chapters.append({
                "chapter_number": ch_num,
                "title": title_text,
                "source_url": href,
                "image_urls": image_urls,
            })

        return chapters

    def _extract_chapter_number(self, href: str, title: str) -> float | None:
        """Extract chapter number from URL or link text."""
        # Try URL first: /chapter-123/ or /chapter/123/
        match = re.search(r'chapter[-/]?(\d+(?:\.\d+)?)', href)
        if match:
            return float(match.group(1))

        # Try title: "Chapter 123" or "Ch. 123"
        match = re.search(r'(?:chapter|ch\.?)\s*(\d+(?:\.\d+)?)', title, re.I)
        if match:
            return float(match.group(1))

        return None

    async def _get_chapter_images(self, chapter_url: str) -> list[str]:
        """Scrape all image URLs from a chapter page."""
        html = await self._get(chapter_url)
        if not html:
            return []

        tree = HTMLParser(html)
        image_urls = []

        # Find images in reader - try multiple selectors
        for img in tree.css(".reader img, .chapter-content img, .chapter-image img, .imgch img"):
            src = img.attributes.get("src", "") or img.attributes.get("data-src", "")
            if src and src.startswith("http"):
                # Filter out ads/trackers
                if not any(bad in src for bad in ["ads", "tracker", "banner", "logo"]):
                    image_urls.append(src)

        return image_urls


class ReaperScraper(BaseScraper):
    """Scraper for Reaper Scans (reaper-scans.com)."""

    name = "reaper"
    BASE = "https://reaper-scans.com"

    def extract_slug(self, url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1]

    async def get_series(self, url: str) -> dict:
        html = await self._get(url)
        if not html:
            return {}

        tree = HTMLParser(html)

        title = ""
        cover_url = ""
        description = ""
        author = ""
        tags = []
        status = "ongoing"

        title_elem = tree.css_first(".entry-title, .manga-title h1, .post-title")
        if title_elem:
            title = title_elem.text(strip=True)

        cover_elem = tree.css_first(".manga-thumb img, .post-thumb img, .img-responsive")
        if cover_elem:
            cover_url = cover_elem.attributes.get("src", "")

        desc_elem = tree.css_first(".post-content p, .entry-content p, .manga-description p")
        if desc_elem:
            description = desc_elem.text(strip=True)[:500]

        author_elem = tree.css_first(".author a, .manga-author")
        if author_elem:
            author = author_elem.text(strip=True)

        for tag in tree.css(".genre a, .post-tags a, .category a"):
            tag_text = tag.text(strip=True).lower()
            if tag_text:
                tags.append(tag_text)

        return {
            "title": title,
            "cover_url": cover_url,
            "description": description,
            "author": author,
            "status": status,
            "tags": tags,
        }

    async def get_chapters(self, url: str) -> list[dict]:
        html = await self._get(url)
        if not html:
            return []

        tree = HTMLParser(html)
        chapters = []

        chapter_links = tree.css(".chapter-list a, .chapter-box a, a[href*='/chapter']")

        for link in chapter_links:
            href = link.attributes.get("href", "")
            title_text = link.text(strip=True)

            if not href:
                continue

            ch_num = self._extract_chapter_number(href, title_text)
            if ch_num is None:
                continue

            image_urls = await self._get_chapter_images(href)

            chapters.append({
                "chapter_number": ch_num,
                "title": title_text,
                "source_url": href,
                "image_urls": image_urls,
            })

        return chapters

    def _extract_chapter_number(self, href: str, title: str) -> float | None:
        match = re.search(r'chapter[-/]?(\d+(?:\.\d+)?)', href)
        if match:
            return float(match.group(1))
        match = re.search(r'(?:chapter|ch\.?)\s*(\d+(?:\.\d+)?)', title, re.I)
        if match:
            return float(match.group(1))
        return None

    async def _get_chapter_images(self, chapter_url: str) -> list[str]:
        html = await self._get(chapter_url)
        if not html:
            return []

        tree = HTMLParser(html)
        image_urls = []

        for img in tree.css(".reader img, .chapter-content img, .chapter-img img, .main_img img"):
            src = img.attributes.get("src", "") or img.attributes.get("data-src", "")
            if src and src.startswith("http"):
                if not any(bad in src for bad in ["ads", "tracker", "banner", "logo"]):
                    image_urls.append(src)

        return image_urls


class FlameScraper(BaseScraper):
    """Scraper for Flame Comics (flamecomics.com)."""

    name = "flame"
    BASE = "https://flamecomics.com"

    def extract_slug(self, url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1]

    async def get_series(self, url: str) -> dict:
        html = await self._get(url)
        if not html:
            return {}

        tree = HTMLParser(html)

        title = ""
        cover_url = ""
        description = ""
        author = ""
        tags = []
        status = "ongoing"

        title_elem = tree.css_first(".entry-title, .comic-title, .post-title h1")
        if title_elem:
            title = title_elem.text(strip=True)

        cover_elem = tree.css_first(".comic-thumb img, .post-thumb img, .cover img")
        if cover_elem:
            cover_url = cover_elem.attributes.get("src", "")

        desc_elem = tree.css_first(".comic-description p, .entry-content p")
        if desc_elem:
            description = desc_elem.text(strip=True)[:500]

        for tag in tree.css(".genre a, .tags a, .comic-tags a"):
            tag_text = tag.text(strip=True).lower()
            if tag_text:
                tags.append(tag_text)

        return {
            "title": title,
            "cover_url": cover_url,
            "description": description,
            "author": author,
            "status": status,
            "tags": tags,
        }

    async def get_chapters(self, url: str) -> list[dict]:
        html = await self._get(url)
        if not html:
            return []

        tree = HTMLParser(html)
        chapters = []

        chapter_links = tree.css(".chapter-list a, .chapter-item a, a[href*='/chapter']")

        for link in chapter_links:
            href = link.attributes.get("href", "")
            title_text = link.text(strip=True)

            if not href:
                continue

            ch_num = self._extract_chapter_number(href, title_text)
            if ch_num is None:
                continue

            image_urls = await self._get_chapter_images(href)

            chapters.append({
                "chapter_number": ch_num,
                "title": title_text,
                "source_url": href,
                "image_urls": image_urls,
            })

        return chapters

    def _extract_chapter_number(self, href: str, title: str) -> float | None:
        match = re.search(r'chapter[-/]?(\d+(?:\.\d+)?)', href)
        if match:
            return float(match.group(1))
        match = re.search(r'(?:chapter|ch\.?)\s*(\d+(?:\.\d+)?)', title, re.I)
        if match:
            return float(match.group(1))
        return None

    async def _get_chapter_images(self, chapter_url: str) -> list[str]:
        html = await self._get(chapter_url)
        if not html:
            return []

        tree = HTMLParser(html)
        image_urls = []

        for img in tree.css(".reader img, .chapter-content img, .reader-image img, .main-image img"):
            src = img.attributes.get("src", "") or img.attributes.get("data-src", "")
            if src and src.startswith("http"):
                if not any(bad in src for bad in ["ads", "tracker", "banner", "logo"]):
                    image_urls.append(src)

        return image_urls


class ScraperFactory:
    """Factory to get the right scraper for a URL or source name."""

    _scrapers: dict[str, type[BaseScraper]] = {
        "asura": AsuraScraper,
        "reaper": ReaperScraper,
        "flame": FlameScraper,
    }

    # Domain mappings
    _domains: dict[str, type[BaseScraper]] = {
        "asuratoon.com": AsuraScraper,
        "asura-scans.com": AsuraScraper,
        "reaper-scans.com": ReaperScraper,
        "reaperscans.com": ReaperScraper,
        "flamecomics.com": FlameScraper,
        "flame-scans.com": FlameScraper,
    }

    def get(self, source_name: str) -> BaseScraper | None:
        """Get scraper by source name (e.g., 'asura')."""
        cls = self._scrapers.get(source_name)
        return cls() if cls else None

    def get_by_url(self, url: str) -> BaseScraper | None:
        """Get scraper by URL domain."""
        domain = urlparse(url).netloc.lower()
        # Remove www.
        if domain.startswith("www."):
            domain = domain[4:]
        cls = self._domains.get(domain)
        return cls() if cls else None

    @classmethod
    def register(cls, name: str, scraper_cls: type[BaseScraper]):
        """Register a new scraper."""
        cls._scrapers[name] = scraper_cls

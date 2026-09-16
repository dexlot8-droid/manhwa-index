"""
Multi-source manhwa scraper with fallback logic.

Supports:
- Asura Scans (asuratoon.com)
- Abyssrift CDN (abyssrift.com) - shared by multiple WP sites
- Reaper Scans (reaperscans.com)
- Flame Comics (flamecomics.com)

Each series has a primary source and fallback sources.
If primary fails, tries fallbacks in order.
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

        title_elem = tree.css_first(".entry-title")
        if title_elem:
            title = title_elem.text(strip=True)

        cover_elem = tree.css_first(".thumb img")
        if cover_elem:
            cover_url = cover_elem.attributes.get("src", "")

        desc_elem = tree.css_first(".entry-content p")
        if desc_elem:
            description = desc_elem.text(strip=True)[:500]

        author_elem = tree.css_first(".author")
        if author_elem:
            author = author_elem.text(strip=True)

        status_elem = tree.css_first(".status")
        if status_elem:
            status = status_elem.text(strip=True).lower()

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

        chapter_links = tree.css(".eplister a, .chapternum a, .chbox a, a[href*='/chapter']")

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

        for img in tree.css(".reader img, .chapter-content img, .chapter-image img, .imgch img"):
            src = img.attributes.get("src", "") or img.attributes.get("data-src", "")
            if src and src.startswith("http"):
                if not any(bad in src for bad in ["ads", "tracker", "banner", "logo"]):
                    image_urls.append(src)

        return image_urls


class AbyssriftScraper(BaseScraper):
    """
    Scraper for the Abyssrift CDN (abyssrift.com).
    Used by multiple WordPress sites: readnanomachine.com, star-embracingswordmaster.com, etc.
    URL pattern: https://abyssrift.com/{CODE}/{CHAPTER}/{PAGE}.webp
    """

    name = "abyssrift"
    BASE = "https://abyssrift.com"

    def __init__(self, code: str = ""):
        super().__init__()
        self.code = code

    def extract_slug(self, url: str) -> str:
        # For abyssrift, the code is the identifier
        return self.code.lower()

    async def get_series(self, url: str) -> dict:
        """Abyssrift doesn't have series pages - metadata comes from the WP site."""
        return {
            "title": "",
            "cover_url": "",
            "description": "",
            "author": "",
            "status": "ongoing",
            "tags": [],
        }

    async def get_chapters(self, url: str) -> list[dict]:
        """Generate chapter URLs based on the CDN pattern."""
        chapters = []
        for ch in range(1, 330):  # Up to chapter 329
            image_urls = []
            for page in range(1, 20):  # Up to 20 pages per chapter
                img_url = f"https://abyssrift.com/{self.code}/{ch}/{page:02d}.webp"
                # We can't verify each URL without downloading, so we generate them
                image_urls.append(img_url)

            chapters.append({
                "chapter_number": ch,
                "title": f"Chapter {ch}",
                "source_url": f"https://abyssrift.com/{self.code}/{ch}/",
                "image_urls": image_urls,
            })

        return chapters

    async def verify_chapter(self, chapter_number: int) -> bool:
        """Verify if a chapter exists by checking the first image."""
        url = f"https://abyssrift.com/{self.code}/{chapter_number}/01.webp"
        try:
            client = await self._get_client()
            resp = await client.get(url, headers={"Referer": "https://star-embracingswordmaster.com/"})
            return resp.status_code == 200
        except Exception:
            return False


class ReaperScraper(BaseScraper):
    """Scraper for Reaper Scans (reaperscans.com)."""

    name = "reaper"
    BASE = "https://reaperscans.com"

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

        title_elem = tree.css_first(".entry-title, .title, h1")
        if title_elem:
            title = title_elem.text(strip=True)

        cover_elem = tree.css_first(".thumb img, .cover img, img")
        if cover_elem:
            cover_url = cover_elem.attributes.get("src", "")

        desc_elem = tree.css_first(".entry-content p, .description, .summary")
        if desc_elem:
            description = desc_elem.text(strip=True)[:500]

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

        chapter_links = tree.css("a[href*='/chapter'], a[href*='/ch']")

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

        for img in tree.css("img"):
            src = img.attributes.get("src", "") or img.attributes.get("data-src", "")
            if src and src.startswith("http"):
                if not any(bad in src for bad in ["ads", "tracker", "banner", "logo", "icon"]):
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

        title_elem = tree.css_first(".entry-title, .title, h1")
        if title_elem:
            title = title_elem.text(strip=True)

        cover_elem = tree.css_first(".thumb img, .cover img, img")
        if cover_elem:
            cover_url = cover_elem.attributes.get("src", "")

        desc_elem = tree.css_first(".entry-content p, .description")
        if desc_elem:
            description = desc_elem.text(strip=True)[:500]

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

        chapter_links = tree.css("a[href*='/chapter'], a[href*='/ch']")

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

        for img in tree.css("img"):
            src = img.attributes.get("src", "") or img.attributes.get("data-src", "")
            if src and src.startswith("http"):
                if not any(bad in src for bad in ["ads", "tracker", "banner", "logo", "icon"]):
                    image_urls.append(src)

        return image_urls


class MultiSourceScraper:
    """
    Multi-source scraper with fallback logic.
    Tries primary source first, then fallbacks.
    """

    def __init__(self):
        self.scrapers = {
            "asura": AsuraScraper(),
            "abyssrift": AbyssriftScraper(),
            "reaper": ReaperScraper(),
            "flame": FlameScraper(),
        }

    async def close(self):
        for scraper in self.scrapers.values():
            await scraper.close()

    async def scrape_series(self, series) -> dict:
        """
        Scrape a series using its primary source, with fallback.
        Returns dict with series metadata and chapters.
        """
        source = series.source_site
        source_url = series.source_url

        # Try primary source
        result = await self._try_scraper(source, source_url, series.source_id)

        if result and result.get("chapters"):
            return result

        # Try fallback sources
        fallbacks = self._get_fallbacks(source)
        for fallback in fallbacks:
            logger.info(f"Trying fallback {fallback} for {series.title}")
            result = await self._try_scraper(fallback, source_url, series.source_id)
            if result and result.get("chapters"):
                return result

        logger.error(f"All sources failed for {series.title}")
        return {}

    async def _try_scraper(self, source: str, url: str, source_id: str) -> dict:
        """Try a specific scraper."""
        if source == "abyssrift":
            scraper = AbyssriftScraper(code=source_id)
        else:
            scraper = self.scrapers.get(source)

        if not scraper:
            return {}

        try:
            series_data = await scraper.get_series(url)
            chapters = await scraper.get_chapters(url)

            return {
                "series": series_data,
                "chapters": chapters,
                "source": source,
            }
        except Exception as e:
            logger.error(f"Scraper {source} failed: {e}")
            return {}

    def _get_fallbacks(self, primary: str) -> list[str]:
        """Get fallback sources for a given primary source."""
        all_sources = ["asura", "reaper", "flame", "abyssrift"]
        return [s for s in all_sources if s != primary]


# Factory for backward compatibility
class ScraperFactory:
    _scrapers = {
        "asura": AsuraScraper,
        "reaper": ReaperScraper,
        "flame": FlameScraper,
    }

    _domains = {
        "asuratoon.com": "asura",
        "reaperscans.com": "reaper",
        "flamecomics.com": "flame",
    }

    @classmethod
    def get_scraper(cls, url: str):
        domain = urlparse(url).netloc
        scraper_name = cls._domains.get(domain)
        if scraper_name and scraper_name in cls._scrapers:
            return cls._scrapers[scraper_name]()
        return None

    @classmethod
    def get_scraper_by_name(cls, name: str):
        if name in cls._scrapers:
            return cls._scrapers[name]()
        return None

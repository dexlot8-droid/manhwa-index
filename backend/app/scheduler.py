import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from .models import async_session, Series, Chapter, ScrapeLog, init_db
from .scraper import ScraperFactory
from .kv_sync import (
    sync_series, sync_chapter, sync_chapter_list, sync_all_series_list,
    sync_popular, delete_series_from_kv, close as close_kv
)
from .config import SCRAPE_DELAY

logger = logging.getLogger(__name__)


async def scrape_series(series: Series) -> dict:
    """Scrape a single series: metadata + all chapters.

    Returns dict with scrape results.
    """
    factory = ScraperFactory()
    scraper = factory.get(series.source_site)
    if not scraper:
        return {"success": False, "error": f"Unknown source site: {series.source_site}"}

    try:
        # Scrape metadata
        meta = await scraper.get_series(series.source_url)
        if meta:
            series.title = meta.get("title", series.title)
            series.cover_url = meta.get("cover_url", series.cover_url)
            series.description = meta.get("description", series.description)
            series.author = meta.get("author", series.author)
            series.tags = meta.get("tags", [])
            series.status = meta.get("status", series.status)

        # Scrape chapters
        chapters_data = await scraper.get_chapters(series.source_url)

        # Track which chapters we already have (by number)
        existing_chapters: dict[float, Chapter] = {}
        for ch in series.chapters:
            if ch.is_active:
                existing_chapters[ch.chapter_number] = ch

        new_chapters = []
        for ch_data in chapters_data:
            ch_num = ch_data["chapter_number"]
            if ch_num in existing_chapters:
                # Update existing chapter if needed
                existing = existing_chapters[ch_num]
                if len(ch_data.get("image_urls", [])) > existing.image_count:
                    existing.image_urls = ch_data["image_urls"]
                    existing.image_count = len(ch_data["image_urls"])
                    existing.source_url = ch_data.get("source_url", existing.source_url)
                    existing.title = ch_data.get("title", existing.title)
                    new_chapters.append(existing)
            else:
                # Create new chapter
                new_ch = Chapter(
                    series_id=series.id,
                    chapter_number=ch_num,
                    title=ch_data.get("title"),
                    source_url=ch_data["source_url"],
                    image_urls=ch_data.get("image_urls", []),
                    image_count=len(ch_data.get("image_urls", [])),
                )
                new_chapters.append(new_ch)

        series.chapter_count = len([c for c in series.chapters if c.is_active]) + len(new_chapters)
        series.last_scraped = datetime.utcnow()

        return {"success": True, "new_chapters": len(new_chapters), "total_chapters": series.chapter_count}

    except Exception as e:
        logger.error(f"Scrape failed for series {series.slug}: {e}")
        return {"success": False, "error": str(e)}


async def sync_series_to_kv(series: Series) -> None:
    """Sync a series and its chapters to KV."""
    await sync_series(series)
    await sync_chapter_list(series.id, series.chapters)
    for ch in series.chapters:
        if ch.is_active:
            await sync_chapter(ch)
    logger.info(f"Synced series {series.slug} ({series.chapter_count} chapters)")


async def sync_all_series() -> dict:
    """Sync all active series to KV (rebuild the 'all_series' key)."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.is_active == True)
        )
        series_list = result.scalars().all()
        await sync_all_series_list(series_list)
        return {"success": True, "series_count": len(series_list)}


async def run_scrape_job() -> dict:
    """Run the full scrape + sync job."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.is_active == True)
        )
        series_list = result.scalars().all()

        stats = {"scraped": 0, "failed": 0, "new_chapters": 0}

        for series in series_list:
            try:
                scrape_result = await scrape_series(series)
                if scrape_result["success"]:
                    stats["scraped"] += 1
                    stats["new_chapters"] += scrape_result.get("new_chapters", 0)
                    await session.commit()
                    await sync_series_to_kv(series)
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.error(f"Failed to scrape {series.slug}: {e}")
                stats["failed"] += 1

        await sync_all_series()
        return stats


async def add_series(source_url: str) -> dict:
    """Add a new series to the database."""
    factory = ScraperFactory()
    scraper = factory.get_by_url(source_url)
    if not scraper:
        return {"success": False, "error": "Unsupported source site"}

    try:
        # Parse URL to get source info
        source_site = scraper.name
        series_slug = scraper.extract_slug(source_url)

        # Check if already exists
        async with async_session() as session:
            result = await session.execute(
                select(Series).where(Series.slug == series_slug)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return {"success": False, "error": "Series already exists", "series_id": existing.id}

            # Create new series
            new_series = Series(
                slug=series_slug,
                title=series_slug.replace("-", " ").title(),  # placeholder
                source_site=source_site,
                source_id=series_slug,
                source_url=source_url,
            )
            session.add(new_series)
            await session.commit()
            await session.refresh(new_series)

            # Scrape it
            scrape_result = await scrape_series(new_series)
            if scrape_result["success"]:
                await session.commit()
                await sync_series_to_kv(new_series)
                return {
                    "success": True,
                    "series_id": new_series.id,
                    "title": new_series.title,
                    "chapters": scrape_result.get("total_chapters", 0),
                }
            else:
                # Rollback on failure
                await session.delete(new_series)
                await session.commit()
                return {"success": False, "error": scrape_result.get("error", "Scrape failed")}

    except Exception as e:
        logger.error(f"Failed to add series: {e}")
        return {"success": False, "error": str(e)}


async def kill_switch(series_slug: str) -> dict:
    """Instantly deactivate a series and purge it from KV."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.slug == series_slug)
        )
        series = result.scalar_one_or_none()
        if not series:
            return {"success": False, "error": "Series not found"}

        # Mark as inactive
        series.is_active = False
        series.updated_at = datetime.utcnow()

        # Mark chapters as inactive
        chapter_ids = [ch.id for ch in series.chapters if ch.is_active]
        for ch in series.chapters:
            ch.is_active = False

        # Log it
        log = ScrapeLog(
            series_id=series.id,
            action="kill_switch",
            message=f"Series {series_slug} deactivated via kill switch",
        )
        session.add(log)
        await session.commit()

        # Purge from KV
        await delete_series_from_kv(series.id, chapter_ids)
        await sync_all_series()

        return {"success": True, "message": f"Series '{series_slug}' deactivated and purged"}

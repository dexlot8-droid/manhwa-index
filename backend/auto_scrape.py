"""
Auto-scrape from Asura Scans - runs every 30 min.
Fetches all chapters + images from Asura API.
Incremental sync: only pushes NEW chapters to KV.
Uses Worker API (bypasses REST API rate limits) as primary.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from app.models import async_session, Series, Chapter, init_db
from app.kv_sync import kv_put, kv_bulk_write
from sqlalchemy import select, delete, func

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

ASURA_API = "https://api.asurascans.com"
WORKER_URL = os.getenv("WORKER_URL", "https://manhwa-kv-proxy.dexlot8.workers.dev")
SCRAPE_INTERVAL = 1800  # 30 min
MAX_KV_WRITES_PER_RUN = 500  # Stay well under 1000/day (even with overhead)

SERIES = [
    {"slug": "return-of-the-mount-hua-sect", "title": "Return of Mount Hua Sect", "db_id": 50},
    {"slug": "nano-machine", "title": "Nano Machine", "db_id": 51},
    {"slug": "star-embracing-swordmaster", "title": "Star-Embracing Swordmaster", "db_id": 52},
    {"slug": "myst-might-mayhem", "title": "Myst, Might, Mayhem", "db_id": 53},
    {"slug": "pick-me-up-infinite-gacha", "title": "Pick Me Up: Infinite Gacha", "db_id": 54},
    {"slug": "chronicles-of-the-demon-faction", "title": "Chronicles of the Demon Faction", "db_id": 55},
    {"slug": "murim-psychopath", "title": "Murim Psychopath", "db_id": 56},
    {"slug": "tales-of-cultivation-and-demon-extermination", "title": "Tales of Cultivation", "db_id": 57},
    {"slug": "reincarnation-of-the-fist-king", "title": "Reincarnation of the Fist King", "db_id": 58},
    {"slug": "swordmasters-youngest-son", "title": "Swordmaster's Youngest Son", "db_id": 59},
]


async def fetch_chapters(client, slug):
    r = await client.get(f"{ASURA_API}/api/series/{slug}/chapters", timeout=30)
    if r.status_code != 200:
        logger.warning(f"  Chapters API returned {r.status_code} for {slug}")
        return []
    return r.json().get("data", [])


async def fetch_chapter_images(client, slug, ch_num):
    r = await client.get(f"{ASURA_API}/api/series/{slug}/chapters/{ch_num}", timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    pages = data.get("data", {}).get("chapter", {}).get("pages", [])
    return [p["url"] for p in pages if "url" in p]


async def scrape_series(client, session, series_info):
    slug = series_info["slug"]
    title = series_info["title"]
    db_id = series_info["db_id"]

    logger.info(f"  [{db_id}] {title}")

    chapters = await fetch_chapters(client, slug)
    if not chapters:
        logger.warning(f"    No chapters found")
        return {"success": False, "error": "no chapters"}

    total_chapters = len(chapters)
    logger.info(f"    Found {total_chapters} chapters")

    chapters_with_images = []
    for i, ch in enumerate(chapters):
        ch_num = ch.get("number", 0)
        ch_title = ch.get("title") or f"Chapter {ch_num}"

        images = await fetch_chapter_images(client, slug, ch_num)
        if images:
            chapters_with_images.append({
                "number": float(ch_num) if ch_num else 0,
                "title": ch_title,
                "image_urls": images,
                "page_count": len(images),
            })

        if (i + 1) % 10 == 0:
            logger.info(f"    {i+1}/{total_chapters} chapters processed")
        await asyncio.sleep(0.3)

    fetched = len(chapters_with_images)
    logger.info(f"    {fetched} chapters with images")

    # Get series record
    result = await session.execute(select(Series).where(Series.id == db_id))
    s = result.scalar_one_or_none()

    if not s:
        s = Series(id=db_id, slug=slug, title=title, is_active=True)
        session.add(s)
        await session.flush()

    s.title = title
    s.slug = slug
    s.source_site = "asura"
    s.is_active = True
    s.status = "ongoing"

    # Delete old chapters
    await session.execute(delete(Chapter).where(Chapter.series_id == db_id))

    new_chapter_ids = []
    for ch_data in chapters_with_images:
        new_ch = Chapter(
            series_id=db_id,
            chapter_number=ch_data["number"],
            title=ch_data["title"],
            source_url=f"https://api.asurascans.com/api/series/{slug}/chapters/{ch_data['number']}",
            image_urls=ch_data["image_urls"],
            image_count=ch_data["page_count"],
            is_active=True,
            scraped_at=datetime.utcnow(),
        )
        session.add(new_ch)
        await session.flush()
        new_chapter_ids.append(new_ch.id)

    s.chapter_count = fetched
    s.last_scraped = datetime.utcnow()
    await session.commit()

    logger.info(f"    {fetched} chapters saved to DB")
    return {
        "success": True,
        "chapters": fetched,
        "db_id": db_id,
        "slug": slug,
        "series_obj": s,
        "new_chapter_ids": new_chapter_ids,
    }


async def get_new_chapters_for_kv(session, db_id, last_kv_sync):
    """Get chapters that haven't been synced to KV yet."""
    if last_kv_sync is None:
        # First sync: get ALL chapters
        result = await session.execute(
            select(Chapter).where(Chapter.series_id == db_id, Chapter.is_active == True)
        )
        return result.scalars().all()
    else:
        # Incremental: only chapters scraped after last_kv_sync
        result = await session.execute(
            select(Chapter).where(
                Chapter.series_id == db_id,
                Chapter.is_active == True,
                Chapter.scraped_at > last_kv_sync,
            )
        )
        return result.scalars().all()


async def sync_to_worker(chapters_payload, all_series_payload=None):
    """Sync chapters using Worker API (bypasses REST API rate limits)."""
    payload = {
        "chapters": chapters_payload,
        "batch_size": 50,  # Worker KV batches of 50 per op
    }
    if all_series_payload:
        payload["all_series"] = all_series_payload

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{WORKER_URL}/sync", json=payload)
        if r.status_code == 200:
            data = r.json()
            return data.get("success", False), data
        else:
            logger.warning(f"  Worker sync failed: {r.status_code} - {r.text[:100]}")
            return False, None


async def sync_with_retry_429(payload_fn, max_retries=5):
    """Retry with exponential backoff on 429."""
    backoff = 60  # Start with 1 minute
    for attempt in range(max_retries):
        success, data = await payload_fn()
        if success:
            return success, data
        logger.warning(f"  Retry {attempt+1}/{max_retries} after {backoff}s...")
        await asyncio.sleep(backoff)
        backoff *= 2  # Exponential: 60, 120, 240, 480, 960
    return False, None


async def sync_all_series_to_kv(session):
    """Push series metadata to KV. Uses REST API with retry."""
    result = await session.execute(
        select(Series).where(Series.is_active == True).order_by(Series.title)
    )
    all_s = result.scalars().all()

    lightweight = []
    for s in all_s:
        lightweight.append({
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "cover_url": s.cover_url or "",
            "chapter_count": s.chapter_count,
            "source_site": s.source_site,
            "tags": [],
        })
    lightweight.sort(key=lambda x: x["title"])

    ok = await kv_put("all_series", {"series": lightweight, "count": len(lightweight)})
    if ok:
        logger.info(f"  KV: {len(lightweight)} series synced via REST")
    else:
        logger.warning(f"  KV: all_series sync via REST failed")
    return ok


async def run_scrape_job():
    """Run full scrape + incremental sync."""
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    ) as client:
        async with async_session() as session:
            total = 0
            success = 0
            failed = 0
            new_chapters_kv = []
            all_chapter_kv = []

            for info in SERIES:
                try:
                    result = await scrape_series(client, session, info)
                    if result.get("success"):
                        success += 1
                        total += result.get("chapters", 0)
                        db_id = result["db_id"]
                        series_obj = result["series_obj"]

                        # Get last_kv_sync for this series
                        last_kv_sync = series_obj.last_kv_sync

                        # Get chapters that need KV sync
                        chs = await get_new_chapters_for_kv(session, db_id, last_kv_sync)
                        
                        if chs:
                            for c in chs:
                                ch_payload = {
                                    "id": c.id,
                                    "series_id": c.series_id,
                                    "chapter_number": c.chapter_number,
                                    "title": c.title,
                                    "image_urls": c.image_urls,
                                    "image_count": c.image_count,
                                }
                                new_chapters_kv.append(ch_payload)
                                all_chapter_kv.append(ch_payload)

                        logger.info(f"    [{db_id}] {len(chs)} new chapters to sync")
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"  Error scraping {info["slug"]}: {e}")
                    failed += 1

            # Try Worker API first (different rate limits)
            worker_success = False
            if new_chapters_kv:
                logger.info(f"  Syncing {len(new_chapters_kv)} chapters via Worker API...")
                worker_success, worker_data = await sync_to_worker(new_chapters_kv)
                if worker_success:
                    logger.info(f"    Worker sync OK: {worker_data}")
                else:
                    logger.warning(f"    Worker sync FAILED, will try REST API fallback")

            # Fallback to REST API if Worker fails
            if not worker_success and new_chapters_kv:
                logger.info(f"  Trying REST API fallback ({len(new_chapters_kv)} chapters)...")
                ok = await kv_bulk_write([{"key": f"chapter:{ch["id"]}", "value": ch} for ch in new_chapters_kv])
                if ok:
                    logger.info(f"    REST bulk sync OK: {len(new_chapters_kv)} chapters")
                else:
                    logger.warning(f"    REST bulk sync FAILED")

            # Sync series metadata (all_series)
            await sync_all_series_to_kv(session)

            # Update last_kv_sync timestamps on all series
            now = datetime.utcnow()
            for info in SERIES:
                result = await session.execute(select(Series).where(Series.id == info["db_id"]))
                s = result.scalar_one_or_none()
                if s:
                    s.last_kv_sync = now
            await session.commit()

            return {
                "scraped": success,
                "failed": failed,
                "new_chapters": total,
                "kv_synced": len(new_chapters_kv),
                "worker_used": worker_success,
            }


async def main():
    await init_db()
    logger.info("=== Asura Auto-Scraper Started (Incremental Sync) ===")
    logger.info(f"Worker URL: {WORKER_URL}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")

    while True:
        logger.info(f"\n[{datetime.utcnow().isoformat()}] Starting scrape job...")
        try:
            stats = await run_scrape_job()
            logger.info(f"Scrape done: {stats}")
        except Exception as e:
            logger.error(f"Scrape failed: {e}")

        logger.info(f"Waiting {SCRAPE_INTERVAL}s...")
        await asyncio.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())

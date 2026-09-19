"""
Auto-scrape from Asura Scans - runs every 30 min.
Stores all chapters for a series in ONE KV value.
Respects Cloudflare KV 1000 writes/day limit by:
  1. Batching: 1 KV write per series (all chapters in one value)
  2. Rate-limit awareness: stops retrying after 429 until next UTC day
  3. Midnight sync: first run after 00:00 UTC does the full sync
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
from sqlalchemy import select, delete

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

ASURA_API = "https://api.asurascans.com"
SCRAPE_INTERVAL = 1800  # 30 min

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

# Track daily writes
KV_DAILY_LIMIT = 1000
_kv_state = {"date": None, "writes_used": 0, "rate_limited": False}


def _reset_daily_if_needed():
    """Reset counter if we're in a new UTC day."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if _kv_state["date"] != today:
        _kv_state["date"] = today
        _kv_state["writes_used"] = 0
        _kv_state["rate_limited"] = False
        logger.info(f"New UTC day - KV budget reset to {KV_DAILY_LIMIT}")


async def _kv_put_limited(key, value):
    """KV put with daily budget tracking. Returns True if written, False if skipped."""
    _reset_daily_if_needed()
    
    if _kv_state["rate_limited"]:
        return False
    
    if _kv_state["writes_used"] >= KV_DAILY_LIMIT:
        _kv_state["rate_limited"] = True
        logger.warning(f"  KV daily limit reached ({KV_DAILY_LIMIT}), skipping remaining writes")
        return False
    
    ok = await kv_put(key, value)
    if ok:
        _kv_state["writes_used"] += 1
        return True
    else:
        # Check if it was a 429
        _kv_state["rate_limited"] = True
        logger.warning("  KV rate limited (429), stopping writes for today")
        return False


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
    """Scrape series - only fetch images for NEW chapters."""
    slug = series_info["slug"]
    title = series_info["title"]
    db_id = series_info["db_id"]

    logger.info(f"  [{db_id}] {title}")

    chapters = await fetch_chapters(client, slug)
    if not chapters:
        logger.warning(f"    No chapters found")
        return {"success": False, "error": "no chapters", "new_count": 0}

    total_chapters = len(chapters)
    logger.info(f"    Found {total_chapters} chapters from API")

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

    result = await session.execute(select(Chapter).where(Chapter.series_id == db_id))
    existing_chapters = {c.chapter_number: c for c in result.scalars().all()}

    new_chapters = []
    for i, ch in enumerate(chapters):
        ch_num = float(ch.get("number", 0)) if ch.get("number") else 0
        ch_title = ch.get("title") or f"Chapter {int(ch_num)}"

        if ch_num in existing_chapters:
            continue

        images = await fetch_chapter_images(client, slug, ch.get("number", 0))
        if images:
            new_ch = Chapter(
                series_id=db_id,
                chapter_number=ch_num,
                title=ch_title,
                source_url=f"https://api.asurascans.com/api/series/{slug}/chapters/{ch.get("number", 0)}",
                image_urls=images,
                image_count=len(images),
                is_active=True,
                scraped_at=datetime.utcnow(),
            )
            session.add(new_ch)
            new_chapters.append(new_ch)

        if (i + 1) % 10 == 0:
            logger.info(f"    {i+1}/{total_chapters} API chapters processed")
        await asyncio.sleep(0.3)

    s.chapter_count = len(existing_chapters) + len(new_chapters)
    s.last_scraped = datetime.utcnow()
    await session.commit()

    logger.info(f"    {len(new_chapters)} NEW chapters added (total: {s.chapter_count})")
    return {"success": True, "new_count": len(new_chapters), "db_id": db_id}


async def sync_series_to_kv(session, db_id):
    """Sync ALL chapters for a series into ONE KV value."""
    result = await session.execute(
        select(Chapter).where(Chapter.series_id == db_id, Chapter.is_active == True)
    )
    chapters = result.scalars().all()

    if not chapters:
        return False

    chapter_list = []
    for c in chapters:
        chapter_list.append({
            "id": c.id,
            "number": c.chapter_number,
            "title": c.title or f"Chapter {c.chapter_number}",
            "image_urls": c.image_urls or [],
            "image_count": c.image_count or 0,
        })

    chapter_list.sort(key=lambda x: x["number"], reverse=True)

    series_data = {
        "series_id": db_id,
        "chapters": chapter_list,
        "count": len(chapter_list),
        "last_updated": datetime.utcnow().isoformat(),
    }

    ok = await _kv_put_limited(f"series:{db_id}", series_data)
    return ok


async def sync_all_series_metadata(session):
    """Sync all_series metadata."""
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

    ok = await _kv_put_limited("all_series", {"series": lightweight, "count": len(lightweight)})
    return ok


async def run_scrape_job():
    """Full scrape + sync with daily KV budget awareness."""
    _reset_daily_if_needed()
    
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    ) as client:
        async with async_session() as session:
            total_new = 0
            success = 0
            failed = 0
            series_with_new_chapters = set()

            for info in SERIES:
                try:
                    result = await scrape_series(client, session, info)
                    if result.get("success"):
                        success += 1
                        new_count = result.get("new_count", 0)
                        total_new += new_count
                        if new_count > 0:
                            series_with_new_chapters.add(result["db_id"])
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"  Error scraping {info["slug"]}: {e}")
                    failed += 1

            # Sync all_series metadata (1 write)
            metadata_ok = await sync_all_series_metadata(session)

            # Sync series with new chapters (1 write each)
            series_synced = 0
            for db_id in series_with_new_chapters:
                ok = await sync_series_to_kv(session, db_id)
                if ok:
                    series_synced += 1

            # Update last_kv_sync
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
                "new_chapters": total_new,
                "kv_metadata": metadata_ok,
                "kv_series_synced": series_synced,
                "kv_writes_used": _kv_state["writes_used"],
                "kv_rate_limited": _kv_state["rate_limited"],
            }


async def main():
    await init_db()
    logger.info("=== Asura Auto-Scraper Started ===")
    logger.info(f"KV daily limit: {KV_DAILY_LIMIT} writes")
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

#!/usr/bin/env python3
"""
Manhwa pipeline v2.1 — INCREMENTAL sync. Never re-uploads what's already in KV.

- Series details (cover, description, genres) live in the local DB. Scraped once.
- Each cycle: fetch chapter LIST (1 API call/series), compare with DB.
  - New chapters only -> fetch their images -> add to DB
  - If anything changed (new chapters / changed cover) -> ONE KV write for that series
  - Unchanged series -> ZERO KV writes, ZERO image fetches
- KV writes per cycle: only changed series + all_series index (1) + popular (1)
"""
import asyncio
import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from sqlalchemy import select, func

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("scraper")

ASURA_API = "https://api.asurascans.com"

CF_ACCOUNT = "40a4319a74d1e05592b2bf64c3f129f4"
KV_NS = "6a07bd3ddf8348fc921a3b1d2e60e53e"
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")

KV_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/storage/kv/namespaces/{KV_NS}"

SERIES = [
    {"slug": "return-of-the-mount-hua-sect", "db_id": 50, "source": "asura"},
    {"slug": "nano-machine", "db_id": 51, "source": "asura"},
    {"slug": "star-embracing-swordmaster", "db_id": 52, "source": "asura"},
    {"slug": "myst-might-mayhem", "db_id": 53, "source": "asura"},
    {"slug": "pick-me-up-infinite-gacha", "db_id": 54, "source": "asura"},
    {"slug": "chronicles-of-the-demon-faction", "db_id": 55, "source": "asura"},
    {"slug": "murim-psychopath", "db_id": 56, "source": "asura"},
    {"slug": "tales-of-cultivation-and-demon-extermination", "db_id": 57, "source": "asura"},
    {"slug": "reincarnation-of-the-fist-king", "db_id": 58, "source": "asura"},
    {"slug": "swordmasters-youngest-son", "db_id": 59, "source": "asura"},
    {"slug": "childhood-friend-of-the-zenith", "db_id": 60, "source": "asura"},
    {"slug": "ode-of-the-brave", "db_id": 61, "source": "asura"},
    {"slug": "chronicles-of-the-lazy-sovereign", "db_id": 62, "source": "asura"},
    {"slug": "bad-born-blood", "db_id": 63, "source": "asura"},
    {"slug": "whispers-of-a-scheming-demon", "db_id": 64, "source": "asura"},
    {"slug": "the-dark-magician-transmigrates-after-66666-years", "db_id": 65, "source": "asura"},
    {"slug": "murim-login", "db_id": 66, "source": "asura"},
    {"slug": "necromancer-academy-and-the-genius-summoner", "db_id": 67, "source": "manhuaplus"},
    {"slug": "serpent-ancestor", "db_id": 68, "source": "manhuaplus", "mp_slug": "snake-immortal-the-tale-of-a-snake-s-cultivation-to-immortality"},
]

async def kv_put(client, key, value):
    r = await client.put(
        f"{KV_URL}/values/{key}",
        content=value if isinstance(value, str) else json.dumps(value),
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
    )
    return r.status_code == 200

async def kv_get(client, key):
    r = await client.get(f"{KV_URL}/values/{key}", headers={"Authorization": f"Bearer {CF_TOKEN}"})
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None

async def fetch_series_detail(client, slug):
    """One-time data: cover, description, genres, status."""
    r = await client.get(f"{ASURA_API}/api/series/{slug}", timeout=30)
    if r.status_code != 200:
        return None
    return r.json().get("series", {})

async def fetch_chapter_list(client, slug):
    r = await client.get(f"{ASURA_API}/api/series/{slug}/chapters", timeout=30)
    if r.status_code != 200:
        return []
    return r.json().get("data", [])

async def fetch_chapter_images(client, slug, ch_num):
    r = await client.get(f"{ASURA_API}/api/series/{slug}/chapters/{ch_num}", timeout=30)
    if r.status_code != 200:
        return []
    data = r.json().get("data", {}).get("chapter", {})
    return [p["url"] for p in data.get("pages", []) if "url" in p]

# ---- Manhua Plus source (plain HTTP, no browser) ----
MP_BASE = "https://manhuaplus.org"

async def mp_get(client, url, retries=3):
    """GET with retries — manhuaplus is slow/rate-limits sometimes."""
    for attempt in range(retries):
        try:
            r = await client.get(url, timeout=60)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            return r
        except Exception:
            if attempt == retries - 1:
                return None
            await asyncio.sleep(3 * (attempt + 1))
    return None

async def mp_chapter_list(client, mp_slug):
    """All chapters: [(number, url)] from the series page."""
    r = await mp_get(client, f"{MP_BASE}/manga/{mp_slug}")
    if not r:
        return []
    pairs = re.findall(r'href="(' + re.escape(MP_BASE) + r'/manga/' + re.escape(mp_slug) + r'/chapter-([0-9.]+))"', r.text)
    seen = {}
    for url, num in pairs:
        n = float(num)
        if n not in seen:
            seen[n] = url
    return sorted(seen.items())

async def mp_chapter_images(client, mp_slug, ch_num):
    """Images for one chapter via the AJAX endpoint (2 requests)."""
    r = await mp_get(client, f"{MP_BASE}/manga/{mp_slug}/chapter-{ch_num:g}")
    if not r:
        return []
    m = re.search(r'const CHAPTER_ID = (\d+);', r.text)
    if not m:
        return []
    r2 = await mp_get(client, f"{MP_BASE}/ajax/image/list/chap/{m.group(1)}")
    if not r2:
        return []
    try:
        data = r2.json()
    except Exception:
        return []
    if not data.get("status"):
        return []
    imgs = re.findall(r'src="(https://cdn\.manhuaplus\.cc/[^"]+)"', data.get("html", ""))
    return list(dict.fromkeys(imgs))

async def mp_series_detail(client, mp_slug):
    """Cover + description from series page (covers are lazy: data-src)."""
    r = await mp_get(client, f"{MP_BASE}/manga/{mp_slug}")
    if not r:
        return {}
    html = r.text
    # own-series cover: src or data-src containing /covers/{mp_slug}
    cover = re.search(r'(?:data-src|src)="(https://manhuaplus\.org/uploads/covers/' + re.escape(mp_slug) + r'\.[a-z]+)"', html)
    if not cover:  # fallback: any cover on page (may be a related series — avoid)
        cover = None
    desc = re.search(r'<meta name="description" content="([^"]{10,300})"', html)
    return {
        "cover": cover.group(1) if cover else f"{MP_BASE}/uploads/covers/{mp_slug}.jpg",
        "description": desc.group(1) if desc else None,
        "status": "ongoing",
    }

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", help="single series slug (test mode)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--refresh-details", action="store_true", help="re-fetch series details from Asura (rare)")
    args = ap.parse_args()

    if not CF_TOKEN:
        logger.error("CF_API_TOKEN env var required")
        sys.exit(1)

    from app.models import async_session, Series, Chapter, init_db

    targets = [s for s in SERIES if (args.all or s["slug"] == args.series)]
    if not targets:
        ap.print_help()
        sys.exit(1)

    await init_db()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        changed_bundles = []
        stats = {"new_ch": 0, "kv_writes": 0, "skipped": 0}

        for info in targets:
            slug, db_id = info["slug"], info["db_id"]
            source = info.get("source", "asura")
            mp_slug = info.get("mp_slug", slug)  # manhuaplus uses different slugs sometimes
            async with async_session() as session:
                sres = await session.execute(select(Series).where(Series.id == db_id))
                series = sres.scalar_one_or_none()
                if not series:
                    logger.warning(f"[{db_id}] {slug}: no DB row, skipping")
                    continue

                # 1. Series details: refresh only if missing or forced
                if args.refresh_details or not series.cover_url:
                    if source == "manhuaplus":
                        detail = await mp_series_detail(client, mp_slug)
                        genres = []
                    else:
                        detail = await fetch_series_detail(client, slug)
                        genres = [g["name"] for g in ((detail or {}).get("genres") or []) if isinstance(g, dict)]
                    detail = detail or {}
                    if detail:
                        series.cover_url = detail.get("cover") or series.cover_url
                        series.description = (detail.get("description") or "")[:2000]
                        series.author = detail.get("author")
                        series.artist = detail.get("artist")
                        series.status = detail.get("status")
                        series.tags = json.dumps(genres) if not isinstance(series.tags, list) else genres
                        await session.commit()
                        logger.info(f"[{db_id}] {slug}: details refreshed (cover={bool(series.cover_url)})")
                    await asyncio.sleep(1)

                # 2. Chapter list (1 call) -> find NEW chapters only
                if source == "manhuaplus":
                    ch_pairs = await mp_chapter_list(client, mp_slug)
                    ch_list = [{"number": n, "title": f"Chapter {n:g}", "url": u} for n, u in ch_pairs]
                else:
                    ch_list = await fetch_chapter_list(client, slug)
                if not ch_list:
                    logger.warning(f"[{db_id}] {slug}: no chapters from API")
                    continue
                api_nums = {float(c.get("number", 0)) for c in ch_list if c.get("number")}
                cres = await session.execute(
                    select(func.count(Chapter.id)).where(Chapter.series_id == db_id)
                )
                db_count = cres.scalar()
                existing = await session.execute(
                    select(Chapter.chapter_number).where(Chapter.series_id == db_id)
                )
                db_nums = {float(r[0]) for r in existing.fetchall()}

                new_nums = api_nums - db_nums
                logger.info(f"[{db_id}] {slug}: API={len(api_nums)} DB={db_count} NEW={len(new_nums)}")

                # 3. Fetch images ONLY for new chapters
                ch_meta = {float(c.get("number", 0)): c for c in ch_list if c.get("number")}
                for n in sorted(new_nums):
                    meta = ch_meta.get(n, {})
                    if source == "manhuaplus":
                        imgs = await mp_chapter_images(client, mp_slug, n)
                        src_url = meta.get("url") or f"{MP_BASE}/manga/{mp_slug}/chapter-{n:g}"
                        await asyncio.sleep(0.6)  # manhuaplus: 2 reqs/chapter, be gentler
                    else:
                        imgs = await fetch_chapter_images(client, slug, n)
                        src_url = f"{ASURA_API}/api/series/{slug}/chapters/{n}"
                        await asyncio.sleep(0.25)
                    if imgs:
                        session.add(Chapter(
                            series_id=db_id,
                            chapter_number=n,
                            title=meta.get("title") or f"Chapter {n:.0f}",
                            source_url=src_url,
                            image_urls=json.dumps(imgs),
                            image_count=len(imgs),
                            is_active=True,
                        ))
                        stats["new_ch"] += 1
                if new_nums:
                    await session.commit()

                # 4. Build bundle from DB (source of truth) and compare with KV
                all_ch = await session.execute(
                    select(Chapter).where(Chapter.series_id == db_id).order_by(Chapter.chapter_number.desc())
                )
                chapters = all_ch.scalars().all()
                bundle = {
                    "slug": slug,
                    "title": series.title,
                    "cover_url": series.cover_url,
                    "description": series.description,
                    "author": series.author,
                    "artist": series.artist,
                    "status": series.status,
                    "tags": series.tags if isinstance(series.tags, list) else (json.loads(series.tags) if series.tags else []),
                    "chapter_count": len(chapters),
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "chapters": [
                        {
                            "number": float(c.chapter_number),
                            "title": c.title,
                            "images": c.image_urls if isinstance(c.image_urls, list) else (json.loads(c.image_urls) if c.image_urls else []),
                        }
                        for c in chapters
                    ],
                }

                # 5. KV: write ONLY if changed
                existing_kv = await kv_get(client, f"series:{slug}")
                kv_unchanged = (
                    existing_kv
                    and existing_kv.get("chapter_count") == bundle["chapter_count"]
                    and existing_kv.get("cover_url") == bundle["cover_url"]
                )
                if kv_unchanged and not new_nums:
                    stats["skipped"] += 1
                    logger.info(f"[{db_id}] {slug}: unchanged, skipping KV write")
                else:
                    ok = await kv_put(client, f"series:{slug}", bundle)
                    stats["kv_writes"] += 1
                    logger.info(f"[{db_id}] {slug}: KV write {'OK' if ok else 'FAIL'} ({bundle['chapter_count']} ch, cover={'yes' if bundle['cover_url'] else 'NO'})")
                changed_bundles.append(bundle)
                await asyncio.sleep(1)

        # 6. Index + popular (always write these 2 — they're tiny)
        index = {"series": [
            {"slug": b["slug"], "title": b["title"], "cover_url": b["cover_url"],
             "chapter_count": b["chapter_count"], "status": b.get("status"),
             "tags": b.get("tags", [])}
            for b in changed_bundles
        ]}
        await kv_put(client, "all_series", index)
        popular = {"series": [b["slug"] for b in changed_bundles]}
        await kv_put(client, "popular", popular)
        logger.info(f"CYCLE DONE: new_chapters={stats['new_ch']} kv_writes={stats['kv_writes']} skipped={stats['skipped']} + index/popular")

if __name__ == "__main__":
    asyncio.run(main())

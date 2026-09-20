#!/usr/bin/env python3
"""
Manhwa pipeline v2 — Asura API -> local DB -> Cloudflare KV (bundled writes).

Key fix vs v1: ONE KV value per series (series:<slug> containing all chapters).
This respects KV free tier: 1000 writes/day ROLLING 24h window.
10 series = 10 writes per sync cycle + 1 all_series write = 11 writes/run.
Run every 6h -> 44 writes/day. Massive headroom.

Usage:
  python3 auto_scrape2.py --series nano-machine          # test ONE series
  python3 auto_scrape2.py --all                          # all 10 series
  python3 auto_scrape2.py --all --no-images              # metadata only (fast)
"""
import asyncio
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from sqlalchemy import select, delete

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("scraper")

ASURA_API = "https://api.asurascans.com"

# dexlot8 Cloudflare account (manhwa)
CF_ACCOUNT = "40a4319a74d1e05592b2bf64c3f129f4"
KV_NS = "6a07bd3ddf8348fc921a3b1d2e60e53e"
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")

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

# ---- KV helpers (direct REST, no wrangler) ----
KV_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/storage/kv/namespaces/{KV_NS}"

async def kv_put(client, key, value):
    r = await client.put(
        f"{KV_URL}/values/{key}",
        content=value if isinstance(value, str) else json.dumps(value),
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
    )
    return r.status_code == 200

# ---- Asura API ----
async def fetch_chapters(client, slug):
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

# ---- Core ----
async def scrape_series(client, info, with_images=True):
    slug, title = info["slug"], info["title"]
    logger.info(f"[{info['db_id']}] {title}")

    chapters = await fetch_chapters(client, slug)
    if not chapters:
        logger.warning(f"  no chapters from API for {slug}")
        return None
    logger.info(f"  {len(chapters)} chapters found")

    out = []
    for i, ch in enumerate(chapters):
        ch_num = ch.get("number", 0)
        entry = {
            "number": float(ch_num) if ch_num else 0,
            "title": ch.get("title") or f"Chapter {ch_num}",
            "date": ch.get("created_at", ""),
        }
        if with_images:
            imgs = await fetch_chapter_images(client, slug, ch_num)
            entry["images"] = imgs
            entry["page_count"] = len(imgs)
            await asyncio.sleep(0.25)  # be gentle with Asura
        out.append(entry)
        if (i + 1) % 25 == 0:
            logger.info(f"  {i+1}/{len(chapters)} processed")

    with_img = sum(1 for c in out if c.get("images"))
    logger.info(f"  done: {len(out)} chapters, {with_img} with images")
    return {"slug": slug, "title": title, "chapters": out}

async def sync_series_to_kv(client, bundle):
    """ONE KV write per series — the whole bundle."""
    slug = bundle["slug"]
    payload = {
        "slug": slug,
        "title": bundle["title"],
        "chapter_count": len(bundle["chapters"]),
        "updated": datetime.now(timezone.utc).isoformat(),
        "chapters": bundle["chapters"],
    }
    ok = await kv_put(client, f"series:{slug}", payload)
    logger.info(f"  KV series:{slug} -> {'OK' if ok else 'FAIL'}")
    return ok

async def sync_index(client, bundles):
    index = {
        "series": [
            {
                "slug": b["slug"],
                "title": b["title"],
                "chapter_count": len(b["chapters"]),
            }
            for b in bundles
        ]
    }
    ok = await kv_put(client, "all_series", index)
    logger.info(f"KV all_series ({len(index['series'])} entries) -> {'OK' if ok else 'FAIL'}")
    return ok

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", help="single series slug to test")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-images", action="store_true", help="skip image fetch (metadata only)")
    ap.add_argument("--kv", action="store_true", help="sync to KV (default: just print)")
    args = ap.parse_args()

    if not CF_TOKEN:
        logger.error("CF_API_TOKEN env var required for KV sync")
        sys.exit(1)

    targets = None
    if args.series:
        targets = [s for s in SERIES if s["slug"] == args.series]
        if not targets:
            logger.error(f"unknown series: {args.series}")
            sys.exit(1)
    elif args.all:
        targets = SERIES
    else:
        ap.print_help()
        sys.exit(1)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        bundles = []
        for info in targets:
            b = await scrape_series(client, info, with_images=not args.no_images)
            if b:
                bundles.append(b)
                if args.kv:
                    await sync_series_to_kv(client, b)
            await asyncio.sleep(2)  # between series

        if args.kv and bundles:
            await sync_index(client, bundles)

    logger.info(f"PIPELINE DONE: {len(bundles)}/{len(targets)} series")

if __name__ == "__main__":
    asyncio.run(main())

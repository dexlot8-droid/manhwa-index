"""
Scrape manhwa data from multiple sources and sync to Cloudflare KV.

Sources (in priority order):
1. Jikan API (MyAnimeList) - for manga metadata
2. AniList API - for manhwa/manhwa metadata
3. Manual admin additions via GitHub issues

Usage:
    python scrape_and_sync.py

Environment variables:
    CF_API_TOKEN - Cloudflare API token
    CF_ACCOUNT_ID - Cloudflare account ID  
    CF_KV_NAMESPACE_ID - Cloudflare KV namespace ID
"""

import json
import os
import hashlib
import logging
from datetime import datetime
from typing import Optional

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Cloudflare config from env
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_KV_NAMESPACE_ID = os.getenv("CF_KV_NAMESPACE_ID", "")

CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}"

HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json",
}

# Sources to scrape
SOURCES = {
    "popular_manhwa": [
        {"query": "manhwa", "limit": 20},
        {"query": "manhua", "limit": 10},
        {"query": "manga action fantasy", "limit": 15},
    ],
    "trending": [
        {"query": "trending manga", "limit": 10},
        {"query": "popular manhwa", "limit": 10},
    ],
}

# Manual additions (these are series we want to track)
PRIORITY_SERIES = [
    {"slug": "solo-leveling", "title": "Solo Leveling", "tags": ["action", "fantasy", "adventure"]},
    {"slug": "omniscient-reader", "title": "Omniscient Reader's Viewpoint", "tags": ["fantasy", "sci-fi", "drama"]},
    {"slug": "tower-of-god", "title": "Tower of God", "tags": ["fantasy", "adventure", "mystery"]},
    {"slug": "wind-breaker", "title": "Wind Breaker", "tags": ["action", "sports", "drama"]},
    {"slug": "the-beginning-after-the-end", "title": "The Beginning After The End", "tags": ["fantasy", "action", "adventure"]},
    {"slug": "mercenary-enrollment", "title": "Mercenary Enrollment", "tags": ["action", "drama", "school"]},
    {"slug": "eleceed", "title": "Eleceed", "tags": ["action", "supernatural", "comedy"]},
    {"slug": "unholy-blood", "title": "Unholy Blood", "tags": ["action", "supernatural", "romance"]},
    {"slug": "noblesse", "title": "Noblesse", "tags": ["action", "supernatural", "mystery"]},
    {"slug": "hardcore-leveling-warrior", "title": "Hardcore Leveling Warrior", "tags": ["action", "fantasy", "comedy"]},
    {"slug": "orv", "title": "Omniscient Reader's Viewpoint", "tags": ["fantasy", "drama"]},
    {"slug": "tbate", "title": "The Beginning After The End", "tags": ["fantasy", "action"]},
    {"slug": "dandadan", "title": "Dandadan", "tags": ["action", "supernatural", "comedy"]},
    {"slug": "one-piece", "title": "One Piece", "tags": ["action", "adventure", "fantasy"]},
    {"slug": "berserk", "title": "Berserk", "tags": ["action", "fantasy", "horror"]},
    {"slug": "vinland-saga", "title": "Vinland Saga", "tags": ["action", "adventure", "drama"]},
    {"slug": "solo-leveling-ragnarok", "title": "Solo Leveling: Ragnarok", "tags": ["action", "fantasy"]},
    {"slug": "gosu", "title": "Gosu", "tags": ["action", "martial-arts", "drama"]},
    {"slug": "the-god-of-high-school", "title": "The God of High School", "tags": ["action", "martial-arts", "supernatural"]},
    {"slug": "let-s-play", "title": "Let's Play", "tags": ["romance", "comedy", "slice-of-life"]},
]


async def fetch_jikan(query: str, limit: int = 20) -> list[dict]:
    """Fetch manga data from Jikan API (MyAnimeList)."""
    url = f"https://api.jikan.moe/v4/manga?q={query}&limit={limit}&order_by=popularity&sort=asc"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("data", []):
                    results.append({
                        "title": item.get("title", ""),
                        "slug": item.get("mal_id", ""),
                        "cover_url": item.get("images", {}).get("jpg", {}).get("large_image_url", ""),
                        "description": item.get("synopsis", "")[:500] if item.get("synopsis") else "",
                        "author": ", ".join([a.get("name", "") for a in (item.get("authors", []) or [])]),
                        "status": item.get("status", "ongoing").lower(),
                        "tags": [g.get("name", "").lower() for g in (item.get("genres", []) or [])],
                        "source": "jikan",
                        "mal_id": item.get("mal_id"),
                        "score": item.get("score", 0),
                        "popularity": item.get("popularity", 0),
                    })
                return results
    except Exception as e:
        logger.error(f"Jikan API error for '{query}': {e}")
    return []


async def fetch_anilist(query: str, limit: int = 20) -> list[dict]:
    """Fetch manga data from AniList GraphQL API."""
    graphql = """
    query ($search: String, $perPage: Int) {
        Page(perPage: $perPage) {
            media(search: $search, type: MANGA, sort: POPULARITY_DESC, countryOfOrigin: "KR") {
                id
                title { romaji english native }
                coverImage { large extraLarge }
                description(asHtml: false)
                status
                genres
                popularity
                averageScore
                staff { nodes { name { full } } }
            }
        }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://graphql.anilist.co",
                json={
                    "query": graphql,
                    "variables": {"search": query, "perPage": limit}
                },
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("data", {}).get("Page", {}).get("media", []):
                    results.append({
                        "title": item.get("title", {}).get("english") or item.get("title", {}).get("romaji", ""),
                        "slug": str(item.get("id", "")),
                        "cover_url": item.get("coverImage", {}).get("extraImage", "") or item.get("coverImage", {}).get("large", ""),
                        "description": (item.get("description") or "")[:500],
                        "author": ", ".join([n.get("name", {}).get("full", "") for n in (item.get("staff", {}).get("nodes", [])[:2])]),
                        "status": (item.get("status") or "ongoing").lower(),
                        "tags": item.get("genres", []) or [],
                        "source": "anilist",
                        "anilist_id": item.get("id"),
                        "score": item.get("averageScore", 0),
                        "popularity": item.get("popularity", 0),
                    })
                return results
    except Exception as e:
        logger.error(f"AniList API error for '{query}': {e}")
    return []


async def push_to_kv(key: str, value: dict) -> bool:
    """Push a single key-value pair to Cloudflare KV."""
    if not CF_API_TOKEN:
        logger.warning("CF_API_TOKEN not set, skipping KV write")
        return False
    
    url = f"{CF_BASE}/values/{key}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=HEADERS, content=json.dumps(value))
        if resp.status_code == 200:
            return True
        else:
            logger.error(f"KV write failed for {key}: {resp.status_code} {resp.text[:200]}")
            return False


async def kv_bulk_write(entries: list[dict]) -> bool:
    """Bulk write multiple KV entries."""
    if not CF_API_TOKEN:
        return False
    
    url = f"{CF_BASE}/bulk"
    payload = [{"key": e["key"], "value": json.dumps(e["value"])} for e in entries]
    
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.put(url, headers=HEADERS, json=payload)
        return resp.status_code == 200


async def main():
    logger.info("Starting manhwa data scrape...")
    
    # 1. Add priority series
    all_series = []
    for s in PRIORITY_SERIES:
        all_series.append({
            "slug": s["slug"],
            "title": s["title"],
            "cover_url": f"https://cover.nep.li/cover/{s['slug']}.jpg",
            "description": f"Manhwa: {s['title']}",
            "author": "",
            "status": "ongoing",
            "tags": s["tags"],
            "chapter_count": 0,
            "source": "admin",
        })
    
    # 2. Fetch from Jikan API
    logger.info("Fetching from Jikan API...")
    for source_name, queries in SOURCES.items():
        for q in queries:
            results = await fetch_jikan(q["query"], q["limit"])
            for r in results:
                # Deduplicate by slug
                existing_slugs = {s["slug"] for s in all_series}
                if r["slug"] not in existing_slugs:
                    all_series.append(r)
            logger.info(f"Jikan '{q['query']}': got {len(results)} results")
    
    # 3. Fetch from AniList API
    logger.info("Fetching from AniList API...")
    for q in [("manhwa", 15), ("manga", 15)]:
        results = await fetch_anilist(q[0], q[1])
        for r in results:
            existing_slugs = {s["slug"] for s in all_series}
            if r["slug"] not in existing_slugs:
                all_series.append(r)
        logger.info(f"AniList '{q[0]}': got {len(results)} results")
    
    # 4. Write to KV
    logger.info(f"Writing {len(all_series)} series to KV...")
    
    # Build lightweight list for all_series
    lightweight = [
        {
            "slug": s["slug"],
            "title": s["title"],
            "cover_url": s["cover_url"],
            "chapter_count": s.get("chapter_count", 0),
            "source": s.get("source", ""),
            "tags": s.get("tags", []),
            "status": s.get("status", "ongoing"),
            "score": s.get("score", 0),
            "popularity": s.get("popularity", 0),
        }
        for s in all_series
    ]
    # Sort by popularity
    lightweight.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    
    # Push all_series list
    await push_to_kv("all_series", {"series": lightweight, "count": len(lightweight)})
    
    # Push popular (top 20)
    await push_to_kv("popular", {"series": [s["slug"] for s in lightweight[:20]]})
    
    # Push each series individually
    entries = []
    for s in all_series:
        entries.append({"key": f"series:{s['slug']}", "value": s})
    
    # Bulk write
    await kv_bulk_write(entries)
    
    # 5. Save artifact
    os.makedirs("data", exist_ok=True)
    with open("data/manhwa.json", "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat(),
            "count": len(all_series),
            "series": all_series,
        }, f, indent=2)
    
    logger.info(f"Done! Scraped {len(all_series)} series.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

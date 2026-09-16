"""
Scrape manhwa data and sync to Cloudflare KV.
Filters: action, fantasy, adventure, martial-arts, supernatural, comedy, drama, slice-of-life.
"""

import json
import os
import logging
from datetime import datetime

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_KV_NAMESPACE_ID = os.getenv("CF_KV_NAMESPACE_ID", "")

CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}"

HEADERS_CF = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json",
}

# Whitelist genres
SFW_TAGS = {"action", "adventure", "fantasy", "martial arts", "supernatural", "comedy", "drama", "slice of life", "sci-fi", "mystery", "romance", "school", "isekai", "shounen", "seinen", "sol", "murim"}
# Blacklist
NSFW_TAGS = {"hentai", "ecchi", "adult", "smut", "yaoi", "yuri"}

# Priority series from admin
PRIORITY_SERIES = [
    {"slug": "solo-leveling", "title": "Solo Leveling", "tags": ["action", "fantasy", "adventure"]},
    {"slug": "omniscient-reader", "title": "Omniscient Reader's Viewpoint", "tags": ["fantasy", "sci-fi", "drama"]},
    {"slug": "tower-of-god", "title": "Tower of God", "tags": ["fantasy", "adventure", "mystery"]},
    {"slug": "wind-breaker", "title": "Wind Breaker", "tags": ["action", "sports", "drama"]},
    {"slug": "the-beginning-after-the-end", "title": "The Beginning After The End", "tags": ["fantasy", "action"]},
    {"slug": "mercenary-enrollment", "title": "Mercenary Enrollment", "tags": ["action", "drama"]},
    {"slug": "eleceed", "title": "Eleceed", "tags": ["action", "supernatural", "comedy"]},
    {"slug": "unholy-blood", "title": "Unholy Blood", "tags": ["action", "supernatural", "romance"]},
    {"slug": "noblesse", "title": "Noblesse", "tags": ["action", "supernatural", "mystery"]},
    {"slug": "hardcore-leveling-warrior", "title": "Hardcore Leveling Warrior", "tags": ["action", "fantasy"]},
    {"slug": "dandadan", "title": "Dandadan", "tags": ["action", "supernatural", "comedy"]},
    {"slug": "one-piece", "title": "One Piece", "tags": ["action", "adventure", "fantasy"]},
    {"slug": "berserk", "title": "Berserk", "tags": ["action", "fantasy", "drama"]},
    {"slug": "vinland-saga", "title": "Vinland Saga", "tags": ["action", "adventure", "drama"]},
    {"slug": "solo-leveling-ragnarok", "title": "Solo Leveling: Ragnarok", "tags": ["action", "fantasy"]},
    {"slug": "gosu", "title": "Gosu", "tags": ["action", "martial-arts", "drama"]},
    {"slug": "the-god-of-high-school", "title": "The God of High School", "tags": ["action", "martial-arts", "supernatural"]},
]


def is_sfw(tags: list[str]) -> bool:
    """Check if the tags are SFW."""
    for tag in tags:
        tag_lower = tag.lower()
        for nsfw in NSFW_TAGS:
            if nsfw in tag_lower:
                return False
    return True


async def fetch_anilist(query: str, limit: int = 25, country: str = "KR") -> list[dict]:
    """Fetch from AniList GraphQL."""
    graphql = """
    query ($search: String, $perPage: Int, $country: CountryCode) {
        Page(perPage: $perPage) {
            media(search: $search, type: MANGA, sort: POPULARITY_DESC, countryOfOrigin: $country) {
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
                json={"query": graphql, "variables": {"search": query, "perPage": limit, "country": country}},
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("data", {}).get("Page", {}).get("media", []):
                    title = item.get("title", {}).get("english") or item.get("title", {}).get("romaji", "")
                    tags = item.get("genres", []) or []
                    
                    # Skip NSFW
                    if not is_sfw(tags):
                        continue
                    
                    # Skip if no tags overlap with SFW_TAGS
                    if not any(t.lower() in SFW_TAGS for t in tags):
                        continue
                    
                    results.append({
                        "title": title,
                        "slug": f"al-{item.get('id', '')}",
                        "cover_url": item.get("coverImage", {}).get("extraLarge", "") or item.get("coverImage", {}).get("large", ""),
                        "description": (item.get("description") or "")[:500],
                        "author": ", ".join([n.get("name", {}).get("full", "") for n in (item.get("staff", {}).get("nodes", [])[:2])]),
                        "status": (item.get("status") or "ongoing").lower(),
                        "tags": [t.lower() for t in tags],
                        "source": "anilist",
                        "score": item.get("averageScore", 0),
                        "popularity": item.get("popularity", 0),
                    })
                return results
    except Exception as e:
        logger.error(f"AniList error: {e}")
    return []


async def push_to_kv(key: str, value: dict) -> bool:
    if not CF_API_TOKEN:
        return False
    url = f"{CF_BASE}/values/{key}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=HEADERS_CF, content=json.dumps(value))
        return resp.status_code == 200


async def kv_bulk_write(entries: list[dict]) -> bool:
    if not CF_API_TOKEN:
        return False
    url = f"{CF_BASE}/bulk"
    payload = [{"key": e["key"], "value": json.dumps(e["value"])} for e in entries]
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.put(url, headers=HEADERS_CF, json=payload)
        return resp.status_code == 200


async def main():
    logger.info("Starting manhwa scrape...")
    all_series = []
    
    # Priority series
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
    
    # Fetch from AniList - Korea
    for q in ["action", "fantasy", "adventure", "martial"]:
        results = await fetch_anilist(q, 25, "KR")
        existing = {s["slug"] for s in all_series}
        for r in results:
            if r["slug"] not in existing:
                all_series.append(r)
        logger.info(f"AniList KR '{q}': {len(results)} results")
    
    # Write to KV
    lightweight = [
        {"slug": s["slug"], "title": s["title"], "cover_url": s["cover_url"],
         "chapter_count": s.get("chapter_count", 0), "source": s.get("source", ""),
         "tags": s.get("tags", []), "status": s.get("status", "ongoing"),
         "score": s.get("score", 0), "popularity": s.get("popularity", 0)}
        for s in all_series
    ]
    lightweight.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    
    await push_to_kv("all_series", {"series": lightweight, "count": len(lightweight)})
    await push_to_kv("popular", {"series": [s["slug"] for s in lightweight[:20]]})
    
    entries = [{"key": f"series:{s['slug']}", "value": s} for s in all_series]
    await kv_bulk_write(entries)
    
    os.makedirs("data", exist_ok=True)
    with open("data/manhwa.json", "w") as f:
        json.dump({"generated_at": datetime.utcnow().isoformat(), "count": len(all_series), "series": all_series}, f, indent=2)
    
    logger.info(f"Done! {len(all_series)} series synced to KV.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

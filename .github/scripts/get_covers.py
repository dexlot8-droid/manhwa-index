"""
Get real cover URLs from AniList and update Cloudflare KV.
"""

import asyncio
import json
import logging
from datetime import datetime

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Series to search on AniList
SERIES = [
    {"slug": "solo-leveling", "search": "Solo Leveling"},
    {"slug": "omniscient-reader", "search": "Omniscient Reader"},
    {"slug": "tower-of-god", "search": "Tower of God"},
    {"slug": "wind-breaker", "search": "Wind Breaker"},
    {"slug": "the-beginning-after-the-end", "search": "The Beginning After The End"},
    {"slug": "mercenary-enrollment", "search": "Mercenary Enrollment"},
    {"slug": "eleceed", "search": "Eleceed"},
    {"slug": "unholy-blood", "search": "Unholy Blood"},
    {"slug": "noblesse", "search": "Noblesse"},
    {"slug": "hardcore-leveling-warrior", "search": "Hardcore Leveling Warrior"},
    {"slug": "dandadan", "search": "Dandadan"},
    {"slug": "one-piece", "search": "One Piece"},
    {"slug": "berserk", "search": "Berserk"},
    {"slug": "vinland-saga", "search": "Vinland Saga"},
    {"slug": "solo-leveling-ragnarok", "search": "Solo Leveling Ragnarok"},
    {"slug": "gosu", "search": "Gosu"},
    {"slug": "the-god-of-high-school", "search": "The God of High School"},
    {"slug": "lookism", "search": "Lookism"},
    {"slug": "reality-quest", "search": "Reality Quest"},
    {"slug": "manager-kim", "search": "Manager Kim"},
    {"slug": "return-of-the-mount-hua", "search": "Return of the Mount Hua"},
    {"slug": "overgeared", "search": "Overgeared"},
    {"slug": "red-storm", "search": "Red Storm"},
    {"slug": "the-player", "search": "The Player"},
    {"slug": "killer-peter", "search": "Killer Peter"},
    {"slug": "lumiere", "search": "Lumiere"},
    {"slug": "snail-male", "search": "Snail Male"},
    {"slug": "love-or-hate", "search": "Love or Hate"},
    {"slug": "for-sake-of-love", "search": "For Sake of Love"},
    {"slug": "meet-my-husband", "search": "Meet My Husband"},
    {"slug": "my-husband-changes-every-night", "search": "My Husband Changes Every Night"},
    {"slug": "the-villain-lives-twice", "search": "The Villain Lives Twice"},
    {"slug": "villain-to-kill", "search": "Villain to Kill"},
    {"slug": "the-world-after-the-fall", "search": "The World After the Fall"},
    {"slug": "summon-the-ai", "search": "Summon the AI"},
    {"slug": "regression-hunter", "search": "Regression Hunter"},
    {"slug": "tower-of-destiny", "search": "Tower of Destiny"},
    {"slug": "return-of-the-legend", "search": "Return of the Legend"},
    {"slug": "legend-of-the-northern-blade", "search": "Legend of the Northern Blade"},
    {"slug": "mookhyang-the-origin", "search": "Mookhyang"},
    {"slug": "murim-login", "search": "Murim Login"},
    {"slug": "max-level-player", "search": "Max Level Player"},
    {"slug": "overlevel", "search": "Overlevel"},
    {"slug": "skeleton-soldier", "search": "Skeleton Soldier"},
    {"slug": "strongest-undertaker", "search": "Strongest Undertaker"},
    {"slug": "duslating-solo", "search": "Duslating Solo"},
    {"slug": "player-1", "search": "Player 1"},
    {"slug": "fFFashion", "search": "FF Fashion King"},
    {"slug": "beat-and-down", "search": "Beat and Down"},
]


async def search_anilist(search: str) -> dict | None:
    """Search for manga on AniList."""
    query = """
    query ($search: String) {
        Page(perPage: 1) {
            media(search: $search, type: MANGA) {
                id
                title { romaji english native }
                coverImage { large extraLarge }
                chapters
                status
                genres
            }
        }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://graphql.anilist.co",
                json={"query": query, "variables": {"search": search}},
                headers={"Content-Type": "application/json"}
            )
            if r.status_code == 200:
                data = r.json()
                media = data.get("data", {}).get("Page", {}).get("media", [])
                if media:
                    return media[0]
    except Exception as e:
        logger.error(f"AniList search failed for '{search}': {e}")
    return None


async def main():
    results = {}
    for s in SERIES:
        result = await search_anilist(s["search"])
        if result:
            results[s["slug"]] = result
            logger.info(f"OK: {s['slug']} -> {result.get('title', {}).get('english', 'N/A')}")
        else:
            logger.warning(f"FAIL: {s['slug']}")
    
    # Save results
    with open("/tmp/anilist_covers.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Found covers for {len(results)}/{len(SERIES)} series")


if __name__ == "__main__":
    asyncio.run(main())

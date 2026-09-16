"""
Seed 10 popular manhwa series for the manhwa-index project.
Uses placeholder covers - real covers will be populated by the VPS scraper.
"""

import asyncio
from datetime import datetime
from app.models import async_session, Series, Chapter, init_db


SERIES = [
    {
        "slug": "return-of-mount-hua-sect",
        "title": "Return of Mount Hua Sect",
        "cover_url": "/img/placeholder.svg",
        "description": "The Mount Hua Sect, once the greatest martial arts sect in the world, has fallen into ruin. A young disciple with the memories of his past life returns to restore the sect to its former glory.",
        "author": "Biga",
        "artist": "Biga",
        "status": "ongoing",
        "tags": ["action", "martial-arts", "fantasy", "reincarnation"],
        "source_site": "asura",
        "source_id": "return-of-mount-hua-sect",
        "source_url": "https://asuratoon.com/manga/return-of-mount-hua-sect/",
        "chapters": 100,
    },
    {
        "slug": "nano-machine",
        "title": "Nano Machine",
        "cover_url": "/img/placeholder.svg",
        "description": "In a world where martial arts and technology coexist, a young man gains access to a mysterious nano machine that enhances his abilities beyond human limits.",
        "author": "Great H",
        "artist": "Great H",
        "status": "ongoing",
        "tags": ["action", "martial-arts", "sci-fi", "fantasy"],
        "source_site": "abyssrift",
        "source_id": "Nano",
        "source_url": "https://w72.readnanomachine.com/",
        "chapters": 329,
    },
    {
        "slug": "star-embracing-swordmaster",
        "title": "Star Embracing Swordmaster",
        "cover_url": "/img/placeholder.svg",
        "description": "A young swordsman with a mysterious star-shaped mark on his hand embarks on a journey to become the greatest swordmaster in the world.",
        "author": "Gwi",
        "artist": "Gwi",
        "status": "ongoing",
        "tags": ["action", "martial-arts", "fantasy", "adventure"],
        "source_site": "abyssrift",
        "source_id": "SES",
        "source_url": "https://star-embracingswordmaster.com/",
        "chapters": 137,
    },
    {
        "slug": "myst-might-mayhem",
        "title": "Myst, Might, Mayhem",
        "cover_url": "/img/placeholder.svg",
        "description": "In a world where mystic powers and might determine one's fate, a young man with a mysterious past rises through the ranks of the martial world.",
        "author": "Unknown",
        "artist": "Unknown",
        "status": "ongoing",
        "tags": ["action", "martial-arts", "fantasy", "mystery"],
        "source_site": "abyssrift",
        "source_id": "MMM",
        "source_url": "https://myst-might-mayhem.com/",
        "chapters": 100,
    },
    {
        "slug": "pick-me-up-infinite-gacha",
        "title": "Pick Me Up: Infinite Gacha",
        "cover_url": "/img/placeholder.svg",
        "description": "A young man discovers a mysterious gacha system that allows him to summon powerful allies and items. With each pull, his power grows exponentially.",
        "author": "Unknown",
        "artist": "Unknown",
        "status": "ongoing",
        "tags": ["action", "fantasy", "system", "adventure"],
        "source_site": "abyssrift",
        "source_id": "Gacha",
        "source_url": "https://pickmeupgacha.com/",
        "chapters": 100,
    },
    {
        "slug": "chronicles-of-the-demon-faction",
        "title": "Chronicles of the Demon Faction",
        "cover_url": "/img/placeholder.svg",
        "description": "In a world where demon factions battle for supremacy, a young warrior with a dark heritage must choose between his demonic nature and his humanity.",
        "author": "Unknown",
        "artist": "Unknown",
        "status": "ongoing",
        "tags": ["action", "fantasy", "demons", "martial-arts"],
        "source_site": "asura",
        "source_id": "chronicles-of-the-demon-faction",
        "source_url": "https://asuratoon.com/manga/chronicles-of-the-demon-faction/",
        "chapters": 100,
    },
    {
        "slug": "murim-psychopath",
        "title": "Murim Psychopath",
        "cover_url": "/img/placeholder.svg",
        "description": "A young man with a twisted mind and unparalleled martial arts talent rises through the murim world, leaving chaos in his wake.",
        "author": "Unknown",
        "artist": "Unknown",
        "status": "ongoing",
        "tags": ["action", "martial-arts", "drama", "psychological"],
        "source_site": "asura",
        "source_id": "murim-psychopath",
        "source_url": "https://asuratoon.com/manga/murim-psychopath/",
        "chapters": 100,
    },
    {
        "slug": "tales-of-cultivation-and-demon-extermination",
        "title": "The Tales of Cultivation and Demon Extermination",
        "cover_url": "/img/placeholder.svg",
        "description": "A cultivator embarks on a journey to exterminate demons and protect the mortal world, facing increasingly powerful foes and uncovering ancient secrets.",
        "author": "Unknown",
        "artist": "Unknown",
        "status": "ongoing",
        "tags": ["action", "fantasy", "cultivation", "demons"],
        "source_site": "asura",
        "source_id": "tales-of-cultivation-and-demon-extermination",
        "source_url": "https://asuratoon.com/manga/tales-of-cultivation-and-demon-extermination/",
        "chapters": 100,
    },
    {
        "slug": "reincarnation-of-the-fist-king",
        "title": "Reincarnation of the Fist King",
        "cover_url": "/img/placeholder.svg",
        "description": "The legendary Fist King is reincarnated in a new world with all his memories and techniques. He must rebuild his power and reclaim his title.",
        "author": "Unknown",
        "artist": "Unknown",
        "status": "ongoing",
        "tags": ["action", "martial-arts", "reincarnation", "fantasy"],
        "source_site": "asura",
        "source_id": "reincarnation-of-the-fist-king",
        "source_url": "https://asuratoon.com/manga/reincarnation-of-the-fist-king/",
        "chapters": 100,
    },
    {
        "slug": "sword-masters-youngest-son",
        "title": "Sword Master's Youngest Son",
        "cover_url": "/img/placeholder.svg",
        "description": "The youngest son of a legendary sword master, long thought to be talentless, discovers a hidden potential that will change the fate of his family.",
        "author": "Unknown",
        "artist": "Unknown",
        "status": "ongoing",
        "tags": ["action", "martial-arts", "fantasy", "family"],
        "source_site": "asura",
        "source_id": "sword-masters-youngest-son",
        "source_url": "https://asuratoon.com/manga/sword-masters-youngest-son/",
        "chapters": 100,
    },
]


async def seed():
    await init_db()
    async with async_session() as session:
        for s in SERIES:
            # Check if series exists
            existing = await session.execute(
                select(Series).where(Series.slug == s["slug"])
            )
            if existing.scalar_one_or_none():
                print(f"  Skipping {s['title']} (already exists)")
                continue

            series = Series(
                slug=s["slug"],
                title=s["title"],
                cover_url=s["cover_url"],
                description=s["description"],
                author=s["author"],
                artist=s["artist"],
                status=s["status"],
                tags=s["tags"],
                source_site=s["source_site"],
                source_id=s["source_id"],
                source_url=s["source_url"],
                chapter_count=s["chapters"],
                is_active=True,
                last_scraped=datetime.utcnow(),
            )
            session.add(series)
            await session.flush()

            # Add sample chapters
            for ch_num in range(1, min(s["chapters"] + 1, 11)):
                ch = Chapter(
                    series_id=series.id,
                    chapter_number=ch_num,
                    title=f"Chapter {ch_num}",
                    source_url=f"{s['source_url']}chapter-{ch_num}/",
                    image_urls=[],
                    image_count=0,
                    is_active=True,
                    scraped_at=datetime.utcnow(),
                )
                session.add(ch)

            print(f"  Added {s['title']} ({s['chapters']} chapters)")

        await session.commit()
        print(f"\nDone! Seeded {len(SERIES)} series.")


if __name__ == "__main__":
    from sqlalchemy import select
    asyncio.run(seed())

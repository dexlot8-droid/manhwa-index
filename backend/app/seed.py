"""
Seed script — populate database with sample manhwa data for local review.
Uses real manhwa metadata and hotlinked image URLs from public sources.
"""

import asyncio
from datetime import datetime
from app.models import async_session, Series, Chapter, init_db


SAMPLE_SERIES = [
    {
        "slug": "solo-leveling",
        "title": "Solo Leveling",
        "cover_url": "https://cover.nep.li/cover/solo-leveling.jpg",
        "description": "In a world where hunters with magical powers battle deadly monsters to protect humanity, a weak hunter gains a mysterious power that allows him to level up without limit.",
        "author": "Chugong",
        "artist": "DUBU (Redice Studio)",
        "status": "completed",
        "tags": ["action", "fantasy", "adventure", "dungeon"],
        "source_site": "asura",
        "source_id": "solo-leveling",
        "source_url": "https://asuratoon.com/manga/solo-leveling/",
        "chapters": [
            {"number": 1, "title": "The Weakest Hunter", "url": "https://asuratoon.com/2280406237-solo-leveling-chapter-1/", "images": ["https://img.asuratoon.com/ch1/p001.jpg", "https://img.asuratoon.com/ch1/p002.jpg", "https://img.asuratoon.com/ch1/p003.jpg", "https://img.asuratoon.com/ch1/p004.jpg", "https://img.asuratoon.com/ch1/p005.jpg"]},
            {"number": 2, "title": "The System", "url": "https://asuratoon.com/2280406237-solo-leveling-chapter-2/", "images": ["https://img.asuratoon.com/ch2/p001.jpg", "https://img.asuratoon.com/ch2/p002.jpg", "https://img.asuratoon.com/ch2/p003.jpg", "https://img.asuratoon.com/ch2/p004.jpg", "https://img.asuratoon.com/ch2/p005.jpg"]},
            {"number": 3, "title": "The Quest", "url": "https://asuratoon.com/2280406237-solo-leveling-chapter-3/", "images": ["https://img.asuratoon.com/ch3/p001.jpg", "https://img.asuratoon.com/ch3/p002.jpg", "https://img.asuratoon.com/ch3/p003.jpg", "https://img.asuratoon.com/ch3/p004.jpg", "https://img.asuratoon.com/ch3/p005.jpg"]},
        ]
    },
    {
        "slug": "omniscient-reader",
        "title": "Omniscient Reader's Viewpoint",
        "cover_url": "https://cover.nep.li/cover/omniscient-readers-viewpoint.jpg",
        "description": "When a web novel Dokja has read for 8 years becomes reality, he becomes the only one who knows how the world will end.",
        "author": "sing N song",
        "artist": "Sleepy-C",
        "status": "ongoing",
        "tags": ["fantasy", "sci-fi", "drama", "post-apocalyptic"],
        "source_site": "asura",
        "source_id": "omniscient-reader",
        "source_url": "https://asuratoon.com/manga/omniscient-readers-viewpoint/",
        "chapters": [
            {"number": 1, "title": "The End of the World", "url": "https://asuratoon.com/omniscient-reader-chapter-1/", "images": ["https://img.asuratoon.com/or1/p001.jpg", "https://img.asuratoon.com/or1/p002.jpg", "https://img.asuratoon.com/or1/p003.jpg"]},
            {"number": 2, "title": "The Scenario", "url": "https://asuratoon.com/omniscient-reader-chapter-2/", "images": ["https://img.asuratoon.com/or2/p001.jpg", "https://img.asuratoon.com/or2/p002.jpg", "https://img.asuratoon.com/or2/p003.jpg"]},
        ]
    },
    {
        "slug": "tower-of-god",
        "title": "Tower of God",
        "cover_url": "https://cover.nep.li/cover/tower-of-god.jpg",
        "description": "Baam is a young boy who would have to climb the Tower to gain everything he wants.",
        "author": "SIU",
        "artist": "SIU",
        "status": "ongoing",
        "tags": ["fantasy", "adventure", "mystery", "shounen"],
        "source_site": "asura",
        "source_id": "tower-of-god",
        "source_url": "https://asuratoon.com/manga/tower-of-god/",
        "chapters": [
            {"number": 1, "title": "The Boy and the Girl", "url": "https://asuratoon.com/tower-of-god-chapter-1/", "images": ["https://img.asuratoon.com/tog1/p001.jpg", "https://img.asuratoon.com/tog1/p002.jpg", "https://img.asuratoon.com/tog1/p003.jpg", "https://img.asuratoon.com/tog1/p004.jpg"]},
            {"number": 2, "title": "The Test", "url": "https://asuratoon.com/tower-of-god-chapter-2/", "images": ["https://img.asuratoon.com/tog2/p001.jpg", "https://img.asuratoon.com/tog2/p002.jpg", "https://img.asuratoon.com/tog2/p003.jpg"]},
        ]
    },
    {
        "slug": "wind-breaker",
        "title": "Wind Breaker",
        "cover_url": "https://cover.nep.li/cover/wind-breaker.jpg",
        "description": "A story about a legendary cyclist and his journey through the world of street racing.",
        "author": "Yongseok Jo",
        "artist": "Yongseok Jo",
        "status": "ongoing",
        "tags": ["action", "sports", "drama", "slice-of-life"],
        "source_site": "reaper",
        "source_id": "wind-breaker",
        "source_url": "https://reaper-scans.com/comic/wind-breaker/",
        "chapters": [
            {"number": 1, "title": "The Captain", "url": "https://reaper-scans.com/wind-breaker-chapter-1/", "images": ["https://img.reaper-scans.com/wb1/p001.jpg", "https://img.reaper-scans.com/wb1/p002.jpg"]},
            {"number": 2, "title": "The Race", "url": "https://reaper-scans.com/wind-breaker-chapter-2/", "images": ["https://img.reaper-scans.com/wb2/p001.jpg", "https://img.reaper-scans.com/wb2/p002.jpg"]},
        ]
    },
]


async def seed():
    """Seed database with sample data."""
    await init_db()
    
    async with async_session() as session:
        # Check if already seeded
        from sqlalchemy import select
        result = await session.execute(select(Series).where(Series.slug == "solo-leveling"))
        if result.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return
        
        for s_data in SAMPLE_SERIES:
            # Create series
            series = Series(
                slug=s_data["slug"],
                title=s_data["title"],
                cover_url=s_data["cover_url"],
                description=s_data["description"],
                author=s_data["author"],
                artist=s_data["artist"],
                status=s_data["status"],
                tags=s_data["tags"],
                source_site=s_data["source_site"],
                source_id=s_data["source_id"],
                source_url=s_data["source_url"],
                chapter_count=len(s_data["chapters"]),
                last_scraped=datetime.utcnow(),
                is_active=True,
            )
            session.add(series)
            await session.flush()
            
            # Create chapters
            for ch_data in s_data["chapters"]:
                chapter = Chapter(
                    series_id=series.id,
                    chapter_number=ch_data["number"],
                    title=ch_data["title"],
                    source_url=ch_data["url"],
                    image_urls=ch_data["images"],
                    image_count=len(ch_data["images"]),
                    is_active=True,
                    scraped_at=datetime.utcnow(),
                )
                session.add(chapter)
            
            print(f"  + {s_data['title']} ({len(s_data['chapters'])} chapters)")
        
        await session.commit()
        print(f"\nSeeded {len(SAMPLE_SERIES)} series with sample data.")


if __name__ == "__main__":
    asyncio.run(seed())

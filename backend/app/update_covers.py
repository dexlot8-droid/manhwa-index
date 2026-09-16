import asyncio
import json
from datetime import datetime
from app.models import async_session, Series, Chapter, init_db
from app.kv_sync import sync_all_series_list, sync_series, close
from sqlalchemy import select

async def main():
    await init_db()
    async with async_session() as session:
        # Load anilist data
        with open("/tmp/anilist_covers.json") as f:
            covers = json.load(f)
        
        # Update series with real covers
        updated = 0
        for slug, info in covers.items():
            result = await session.execute(select(Series).where(Series.slug == slug))
            series = result.scalar_one_or_none()
            if series:
                series.cover_url = info["coverImage"]["large"]
                series.cover_url = info["coverImage"]["large"]
                if info.get("chapters"):
                    series.chapter_count = info["chapters"]
                updated += 1
        
        await session.commit()
        print(f"Updated {updated} covers")
        
        # Add sample chapters for series that have >0 chapters
        result = await session.execute(select(Series).where(Series.is_active == True))
        series_list = result.scalars().all()
        
        for s in series_list:
            if s.chapter_count > 0 and not s.chapters:
                # Add 5 sample chapters
                for i in range(1, 6):
                    ch = Chapter(
                        series_id=s.id,
                        chapter_number=i,
                        title=f"Chapter {i}",
                        source_url=f"https://example.com/{s.slug}/ch{i}",
                        image_urls=[
                            f"https://cover.nep.li/page/{s.id}/{i}/1.jpg",
                            f"https://cover.nep.li/page/{s.id}/{i}/2.jpg",
                        ],
                        image_count=2,
                        is_active=True,
                        scraped_at=datetime.utcnow(),
                    )
                    session.add(ch)
        
        await session.commit()
        
        # Sync to KV
        await sync_all_series_list(series_list)
        for s in series_list:
            await sync_series(s)
        print(f"Synced {len(series_list)} to KV")
    await close()

if __name__ == "__main__":
    asyncio.run(main())

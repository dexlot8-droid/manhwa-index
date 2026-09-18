import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.models import async_session, Series, init_db
from app.kv_sync import kv_put, kv_bulk_write
from sqlalchemy import select

async def main():
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(Series).where(Series.is_active == True))
        all_s = result.scalars().all()
        for s in all_s:
            await session.refresh(s, ["chapters"])
            ch_list = [
                {"id": c.id, "number": c.chapter_number, "title": c.title or f"Ch. {c.chapter_number}"}
                for c in sorted(s.chapters, key=lambda x: x.chapter_number, reverse=True)
                if c.is_active
            ]
            kv_data = {
                "id": s.id,
                "slug": s.slug,
                "title": s.title,
                "cover_url": s.cover_url or "",
                "description": "",
                "author": "",
                "status": s.status,
                "tags": [],
                "chapter_count": s.chapter_count,
                "chapters": ch_list,
            }
            await kv_put(f"series:{s.slug}", kv_data)
            await kv_put(f"series:{s.id}", kv_data)
            print(f"  Synced {s.title[:40]} cover={s.cover_url[:50] if s.cover_url else NONE}")
        print(f"\nDone: {len(all_s)} series synced to KV with covers")

if __name__ == "__main__":
    asyncio.run(main())

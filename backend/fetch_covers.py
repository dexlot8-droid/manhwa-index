import asyncio, json, os, sys, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.models import async_session, Series, init_db
from sqlalchemy import select

SERIES = [
    {"slug": "return-of-the-mount-hua-sect", "db_id": 50, "source": "asura"},
    {"slug": "nano-machine", "db_id": 51, "source": "asura"},
    {"slug": "star-embracing-swordmaster", "db_id": 52, "source": "asura"},
    {"slug": "myst-might-mayhem", "db_id": 53, "source": "mangadex"},
    {"slug": "pick-me-up-infinite-gacha", "db_id": 54, "source": "asura"},
    {"slug": "chronicles-of-the-demon-faction", "db_id": 55, "source": "asura"},
    {"slug": "murim-psychopath", "db_id": 56, "source": "asura"},
    {"slug": "tales-of-cultivation-and-demon-extermination", "db_id": 57, "source": "none"},
    {"slug": "reincarnation-of-the-fist-king", "db_id": 58, "source": "mangadex"},
    {"slug": "swordmasters-youngest-son", "db_id": 59, "source": "mangadex"},
]

COVERS = {
    50: "https://cdn.asurascans.com/asura-images/covers/return-of-the-mount-hua-sect.c0cbf9.webp",
    51: "https://cdn.asurascans.com/asura-images/covers/nano-machine.e31bdb.webp",
    52: "https://cdn.asurascans.com/asura-images/covers/star-embracing-swordmaster.6b1222.webp",
    53: "https://mangadex.org/covers/df5f8e3d-64a1-4287-8f08-4a732e9cb757/3cd106a7-6354-4832-8c6d-21ed5de163fa.png",
    54: "https://cdn.asurascans.com/asura-images/covers/pick-me-up-infinite-gacha.3ebe61.webp",
    55: "https://cdn.asurascans.com/asura-images/covers/chronicles-of-the-demon-faction.d4dcb8.webp",
    56: "https://cdn.asurascans.com/asura-images/covers/murim-psychopath.60ee5d.webp",
    57: None,
    58: "https://mangadex.org/covers/68626091-4998-402f-a246-d965536813b0/c0dee21f-d87b-4a7a-bacb-794f053463e1.jpg",
    59: "https://mangadex.org/covers/85a8ebda-9959-4244-ad03-a2d9f6a746a2/a2a097a1-1c07-47cf-8252-2a5e8c9fea05.jpg",
}

async def main():
    await init_db()
    async with async_session() as session:
        updated = 0
        for sid, cover in COVERS.items():
            if not cover:
                print(f"  [{sid}] SKIP (no cover found)")
                continue
            result = await session.execute(select(Series).where(Series.id == sid))
            s = result.scalar_one_or_none()
            if s:
                s.cover_url = cover
                updated += 1
                print(f"  [{sid}] {s.title[:40]} -> {cover[:60]}...")
            else:
                print(f"  [{sid}] NOT FOUND IN DB")
        await session.commit()
        print(f"\nUpdated {updated} covers in DB")

if __name__ == "__main__":
    asyncio.run(main())

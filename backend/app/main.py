import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import async_session, init_db, Series, Chapter, ScrapeLog
from .scheduler import add_series, scrape_series, run_scrape_job, kill_switch, sync_all_series
from .kv_sync import close as close_kv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic schemas
class AddSeriesRequest(BaseModel):
    url: str


class KillSwitchRequest(BaseModel):
    slug: str


# Auth dependency
async def verify_admin(request: Request):
    """Simple password auth via header: X-Admin-Token"""
    from .config import ADMIN_PASSWORD
    token = request.headers.get("X-Admin-Token", "")
    if token != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    await close_kv()


app = FastAPI(title="Manhwa Index API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")
    app.mount("/img", StaticFiles(directory=str(frontend_dir / "img")), name="img")


# ============================================
# FRONTEND ROUTES
# ============================================

@app.get("/")
async def index():
    return FileResponse(str(frontend_dir / "index.html"))


@app.get("/series.html")
async def series_page():
    return FileResponse(str(frontend_dir / "series.html"))


@app.get("/chapter.html")
async def chapter_page():
    return FileResponse(str(frontend_dir / "chapter.html"))


# ============================================
# ADMIN ROUTES (Protected)
# ============================================

@app.get("/admin/series", dependencies=[Depends(verify_admin)])
async def admin_list_series():
    """List all series with chapter count."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).order_by(Series.created_at.desc())
        )
        series_list = result.scalars().all()
        return [
            {
                "id": s.id,
                "slug": s.slug,
                "title": s.title,
                "cover_url": s.cover_url,
                "author": s.author,
                "status": s.status,
                "source_site": s.source_site,
                "chapter_count": s.chapter_count,
                "is_active": s.is_active,
                "last_scraped": s.last_scraped.isoformat() if s.last_scraped else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in series_list
        ]


@app.get("/admin/series/{series_id}", dependencies=[Depends(verify_admin)])
async def admin_series_detail(series_id: int):
    """Get full series detail with chapters."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.id == series_id)
        )
        series = result.scalar_one_or_none()
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        return {
            "id": series.id,
            "slug": series.slug,
            "title": series.title,
            "cover_url": series.cover_url,
            "description": series.description,
            "author": series.author,
            "status": series.status,
            "tags": series.tags,
            "source_site": series.source_site,
            "source_url": series.source_url,
            "is_active": series.is_active,
            "chapters": [
                {
                    "id": ch.id,
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "source_url": ch.source_url,
                    "image_count": ch.image_count,
                    "is_active": ch.is_active,
                }
                for ch in series.chapters
            ],
        }


@app.post("/admin/series", dependencies=[Depends(verify_admin)])
async def admin_add_series(request: AddSeriesRequest):
    """Add a new series to the database."""
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")

    result = await add_series(request.url)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed"))
    return result


@app.post("/admin/scrape/{series_id}", dependencies=[Depends(verify_admin)])
async def admin_scrape_series(series_id: int):
    """Trigger a scrape for a specific series."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.id == series_id)
        )
        series = result.scalar_one_or_none()
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        scrape_result = await scrape_series(series)
        await session.commit()
        return scrape_result


@app.post("/admin/scrape-all", dependencies=[Depends(verify_admin)])
async def admin_scrape_all():
    """Run full scrape + sync for all active series."""
    stats = await run_scrape_job()
    return stats


@app.delete("/admin/series/{series_id}", dependencies=[Depends(verify_admin)])
async def admin_kill_switch(series_id: int):
    """Kill switch: deactivate a series and purge from KV."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.id == series_id)
        )
        series = result.scalar_one_or_none()
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        kill_result = await kill_switch(series.slug)
        return kill_result


@app.get("/admin/logs", dependencies=[Depends(verify_admin)])
async def admin_logs(limit: int = 50):
    """Get recent scrape logs."""
    async with async_session() as session:
        result = await session.execute(
            select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(limit)
        )
        logs = result.scalars().all()
        return [
            {
                "id": log.id,
                "series_id": log.series_id,
                "action": log.action,
                "message": log.message,
                "metadata": log.metadata_json,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]


# ============================================
# PUBLIC API (for frontend)
# ============================================

@app.get("/api/series")
async def public_list_series():
    """Public: list all active series."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.is_active == True).order_by(Series.title)
        )
        series_list = result.scalars().all()
        return [
            {
                "id": s.id,
                "slug": s.slug,
                "title": s.title,
                "cover_url": s.cover_url,
                "author": s.author,
                "status": s.status,
                "tags": s.tags,
                "chapter_count": s.chapter_count,
            }
            for s in series_list
        ]


@app.get("/api/series/{series_id}")
async def public_series_detail(series_id: int):
    """Public: get series with active chapters."""
    async with async_session() as session:
        result = await session.execute(
            select(Series).where(Series.id == series_id, Series.is_active == True)
        )
        series = result.scalar_one_or_none()
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        active_chapters = [ch for ch in series.chapters if ch.is_active]
        return {
            "id": series.id,
            "slug": series.slug,
            "title": series.title,
            "cover_url": series.cover_url,
            "description": series.description,
            "author": series.author,
            "status": series.status,
            "tags": series.tags,
            "chapters": [
                {
                    "id": ch.id,
                    "chapter_number": ch.chapter_number,
                    "title": ch.title or f"Chapter {ch.chapter_number}",
                }
                for ch in sorted(active_chapters, key=lambda c: c.chapter_number, reverse=True)
            ],
        }


@app.get("/api/chapter/{chapter_id}")
async def public_chapter_detail(chapter_id: int):
    """Public: get chapter with image URLs."""
    async with async_session() as session:
        result = await session.execute(
            select(Chapter).where(Chapter.id == chapter_id, Chapter.is_active == True)
        )
        chapter = result.scalar_one_or_none()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        return {
            "id": chapter.id,
            "series_id": chapter.series_id,
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "image_urls": chapter.image_urls,
            "image_count": chapter.image_count,
        }


@app.get("/api/stats")
async def public_stats():
    """Public: basic stats."""
    async with async_session() as session:
        series_count = await session.execute(
            select(func.count(Series.id)).where(Series.is_active == True)
        )
        chapter_count = await session.execute(
            select(func.count(Chapter.id)).where(Chapter.is_active == True)
        )
        return {
            "active_series": series_count.scalar(),
            "active_chapters": chapter_count.scalar(),
            "generated_at": datetime.utcnow().isoformat(),
        }


# ============================================
# HEALTH
# ============================================

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

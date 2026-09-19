from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, JSON, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from .config import DATABASE_URL

# Convert sqlite to aiosqlite URL
if DATABASE_URL.startswith("sqlite:///"):
    ASYNC_DB_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    ASYNC_DB_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_DB_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


class Series(Base):
    __tablename__ = "series"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    cover_url = Column(Text)
    description = Column(Text)
    author = Column(String(255))
    artist = Column(String(255))
    status = Column(String(50), default="ongoing")
    tags = Column(JSON, default=[])
    source_site = Column(String(100), nullable=False)
    source_id = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=False)
    chapter_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    last_scraped = Column(DateTime)
    last_kv_sync = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapters = relationship("Chapter", back_populates="series", cascade="all, delete-orphan", lazy="selectin")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Float, nullable=False)
    title = Column(String(500))
    source_url = Column(Text, nullable=False)
    image_urls = Column(JSON, nullable=False, default=[])
    image_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    series = relationship("Series", back_populates="chapters")


class ScrapeLog(Base):
    __tablename__ = "scrape_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(Integer, ForeignKey("series.id", ondelete="SET NULL"))
    action = Column(String(50), nullable=False)
    message = Column(Text)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

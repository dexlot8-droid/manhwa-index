import httpx
import json
import logging
from .config import CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN

logger = logging.getLogger(__name__)

CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}"

_headers = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json",
}

_client: httpx.AsyncClient | None = None


def _has_cf() -> bool:
    return bool(CF_API_TOKEN and CF_ACCOUNT_ID and CF_KV_NAMESPACE_ID)


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=60)
    return _client


async def close():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def kv_put(key: str, value: dict) -> bool:
    if not _has_cf():
        return False
    url = f"{CF_BASE}/values/{key}"
    client = await get_client()
    try:
        resp = await client.put(url, headers=_headers, content=json.dumps(value))
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"KV put failed for {key}: {e}")
        return False


async def kv_get(key: str):
    if not _has_cf():
        return None
    url = f"{CF_BASE}/values/{key}"
    client = await get_client()
    try:
        resp = await client.get(url, headers=_headers)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        logger.error(f"KV get failed for {key}: {e}")
        return None


async def kv_delete(key: str) -> bool:
    if not _has_cf():
        return False
    url = f"{CF_BASE}/values/{key}"
    client = await get_client()
    try:
        resp = await client.delete(url, headers=_headers)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"KV delete failed for {key}: {e}")
        return False


async def kv_bulk_write(entries: list[dict]) -> bool:
    if not _has_cf():
        return False
    url = f"{CF_BASE}/bulk"
    payload = [{"key": e["key"], "value": json.dumps(e["value"])} for e in entries]
    client = await get_client()
    try:
        resp = await client.put(url, headers=_headers, json=payload)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"KV bulk write failed: {e}")
        return False


async def kv_bulk_delete(keys: list[str]) -> bool:
    if not _has_cf():
        return False
    url = f"{CF_BASE}/bulk"
    client = await get_client()
    try:
        resp = await client.request("DELETE", url, headers=_headers, content=json.dumps(keys))
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"KV bulk delete failed: {e}")
        return False


async def sync_series(series_obj) -> bool:
    data = {
        "id": series_obj.id,
        "slug": series_obj.slug,
        "title": series_obj.title,
        "cover_url": series_obj.cover_url,
        "description": series_obj.description,
        "author": series_obj.author,
        "status": series_obj.status,
        "tags": series_obj.tags,
        "source_site": series_obj.source_site,
        "chapter_count": series_obj.chapter_count,
        "last_scraped": series_obj.last_scraped.isoformat() if series_obj.last_scraped else None,
    }
    return await kv_put(f"series:{series_obj.id}", data)


async def sync_chapter(chapter_obj) -> bool:
    data = {
        "id": chapter_obj.id,
        "series_id": chapter_obj.series_id,
        "chapter_number": chapter_obj.chapter_number,
        "title": chapter_obj.title,
        "image_urls": chapter_obj.image_urls,
        "image_count": chapter_obj.image_count,
    }
    return await kv_put(f"chapter:{chapter_obj.id}", data)


async def sync_chapter_list(series_id: int, chapters: list) -> bool:
    lightweight = [
        {"id": ch.id, "number": ch.chapter_number, "title": ch.title or f"Ch. {ch.chapter_number}"}
        for ch in chapters
        if ch.is_active
    ]
    lightweight.sort(key=lambda x: x["number"], reverse=True)
    return await kv_put(f"chapters:{series_id}", {"series_id": series_id, "chapters": lightweight})


async def sync_all_series_list(series_list: list) -> bool:
    lightweight = [
        {
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "cover_url": s.cover_url,
            "chapter_count": s.chapter_count,
            "source_site": s.source_site,
            "tags": s.tags,
        }
        for s in series_list
        if s.is_active
    ]
    lightweight.sort(key=lambda x: x["title"])
    return await kv_put("all_series", {"series": lightweight, "count": len(lightweight)})


async def sync_popular(series_list: list) -> bool:
    return await kv_put("popular", {"series": [s.id for s in series_list[:20]]})


async def delete_series_from_kv(series_id: int, chapter_ids: list[int]) -> bool:
    if not _has_cf():
        return True
    try:
        keys_to_delete = [f"series:{series_id}", f"chapters:{series_id}"]
        keys_to_delete.extend([f"chapter:{cid}" for cid in chapter_ids])
        for i in range(0, len(keys_to_delete), 10000):
            batch = keys_to_delete[i:i+10000]
            await kv_bulk_delete(batch)
        return True
    except Exception as e:
        logger.error(f"Failed to delete series from KV: {e}")
        return False

# Manhwa Index

A lightweight manhwa/manga chapter indexing website. Stores only text image URLs — no image files hosted.

## Architecture

```
User Browser → Cloudflare Pages (frontend) → Cloudflare KV (cached URLs) → Hotlink images
                                     ↓
                          Cloudflare Worker (KV proxy)
                                     ↓
                          Cloudflare Tunnel (outbound only)
                                     ↓
                          Azure VPS (no public IP) → FastAPI admin + scraper + SQLite
```

## Quick Start

### 1. Backend (VPS)

```bash
cd backend
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
DATABASE_URL=sqlite:///./manhwa.db
CF_ACCOUNT_ID=your_cf_account_id
CF_KV_NAMESPACE_ID=your_kv_namespace_id
CF_API_TOKEN=your_cf_api_token
ADMIN_PASSWORD=your_admin_password
SCRAPE_DELAY=1.5
EOF

# Run
python -m app.main
# → http://localhost:8000
```

### 2. Cloudflare Worker

```bash
cd worker
npm install -g wrangler
wrangler login

# Update wrangler.toml with your KV namespace ID
# Create KV namespace:
wrangler kv namespace create MANHWA_KV

# Deploy
wrangler deploy
```

### 3. Frontend (Cloudflare Pages)

```bash
cd frontend
# Deploy via Cloudflare Dashboard:
# 1. Go to Pages → Create project → Upload frontend/ folder
# 2. Or connect to Git repo

# Update api.js with your Worker URL before deploying
```

### 4. Add a Series

```bash
# Add via admin API (password in .env)
curl -X POST http://localhost:8000/admin/series \
  -H "X-Admin-Token: your_admin_password" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://asuratoon.com/manga/solo-leveling/"}'

# Run full scrape + sync to KV
curl -X POST http://localhost:8000/admin/scrape-all \
  -H "X-Admin-Token: your_admin_password"
```

### 5. Kill Switch

```bash
# Deactivate series and purge from KV
curl -X DELETE http://localhost:8000/admin/series/1 \
  -H "X-Admin-Token: your_admin_password"
```

## API Reference

### Public Endpoints
- `GET /api/series` — List all active series
- `GET /api/series/{id}` — Series with active chapters
- `GET /api/chapter/{id}` — Chapter with image URLs
- `GET /api/stats` — Basic stats

### Admin Endpoints (require `X-Admin-Token`)
- `GET /admin/series` — List all series
- `GET /admin/series/{id}` — Full detail with chapters
- `POST /admin/series` — Add new series
- `POST /admin/scrape/{id}` — Scrape single series
- `POST /admin/scrape-all` — Full scrape + sync
- `DELETE /admin/series/{id}` — Kill switch
- `GET /admin/logs` — Recent scrape logs

### KV Worker Endpoints
- `GET /all_series` — All active series (cached)
- `GET /series:{id}` — Single series metadata
- `GET /chapters:{id}` — Chapter list for series
- `GET /chapter:{id}` — Single chapter with image URLs

## Adding New Scrapers

1. Create a new class in `backend/app/scraper.py` extending `BaseScraper`
2. Implement `extract_slug()`, `get_series()`, `get_chapters()`
3. Register in `ScraperFactory._scrapers` and `_domains`

## Security

- VPS has no public IP, all inbound ports blocked
- Cloudflare Tunnel is outbound-only
- Admin panel behind `X-Admin-Token` auth
- Image URLs only — no copyrighted content hosted
- Kill switch for instant DMCA response

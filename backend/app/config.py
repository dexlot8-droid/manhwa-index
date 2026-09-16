import os
from dotenv import load_dotenv

load_dotenv()

# Database (SQLite for now, easy to migrate to Postgres later)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./manhwa.db")

# Cloudflare
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_KV_NAMESPACE_ID = os.getenv("CF_KV_NAMESPACE_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")

# Admin
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Scraping
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.5"))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

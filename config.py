"""Configuration for the Nykaa lip liner scraper."""

from __future__ import annotations

import os
from pathlib import Path

# Environment: dev | test | prod (controls logging verbosity and headless mode)
ENV = os.getenv("SCRAPER_ENV", "dev").lower()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
RAW_API_DIR = BASE_DIR / "data" / "raw_api_responses"

CSV_OUTPUT = OUTPUT_DIR / "lipliners.csv"
JSON_OUTPUT = OUTPUT_DIR / "lipliners.json"
LOG_FILE = LOGS_DIR / "scraper.log"
FAILED_URLS_FILE = LOGS_DIR / "failed_urls.txt"

NYKAA_BASE_URL = "https://www.nykaa.com"
CATEGORY_ID = "251"
CATEGORY_URL = f"{NYKAA_BASE_URL}/makeup/lips/lip-liner/c/{CATEGORY_ID}"
CATEGORY_NAME = "Lip Liner"

LISTING_API_URL = f"{NYKAA_BASE_URL}/app-api/index.php/products/list"
LISTING_API_PARAMS = {
    "category_id": CATEGORY_ID,
    "client": "react",
    "filter_format": "v2",
    "platform": "website",
    "sort": "popularity",
}

# Concurrency and rate limiting
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))
MIN_DELAY_SECONDS = float(os.getenv("MIN_DELAY_SECONDS", "0.5"))
MAX_DELAY_SECONDS = float(os.getenv("MAX_DELAY_SECONDS", "1.5"))

# Retry settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "4"))
RETRY_MIN_WAIT = float(os.getenv("RETRY_MIN_WAIT", "1"))
RETRY_MAX_WAIT = float(os.getenv("RETRY_MAX_WAIT", "10"))

# Playwright
HEADLESS = os.getenv("HEADLESS", "true" if ENV == "prod" else "false").lower() == "true"
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "60000"))
AKAMAI_WAIT_SECONDS = int(os.getenv("AKAMAI_WAIT_SECONDS", "5"))

# Optional proxy (e.g. http://user:pass@host:port)
PROXY = os.getenv("PROXY")

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": CATEGORY_URL,
    "Origin": NYKAA_BASE_URL,
}

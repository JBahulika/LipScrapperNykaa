# Nykaa Lip Liner Scraper

This tool collects all lip liner products from [Nykaa](https://www.nykaa.com), including every shade of each product.

It saves the data as:
- `output/lipliners.csv`
- `output/lipliners.json`

Each row = one shade. So if a product has 5 shades, you get 5 rows.

A full run collects about **156 products** and **700 shades** from **78+ brands**.

---

## What you need

- Python 3.10 or newer
- A working internet connection

---

## Setup

```bash
git clone https://github.com/JBahulika/LipScrapperNykaa.git
cd LipScrapperNykaa

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

---

## How to run

**Test with 5 products first:**
```bash
python scraper.py --limit 5
```

**Run the full scrape:**
```bash
python scraper.py
```

When it's done, check the `output/` folder for your files.

---

## How it works (simple version)

1. Opens a real browser to get past Nykaa's security checks
2. Fetches the list of all lip liner products
3. Visits each product page to get shade details (name, price, image, stock, etc.)
4. Saves everything to CSV and JSON

The whole scrape usually takes **3–8 minutes**.

---

## What data you get

Each row has these fields:

| Field | What it means |
|-------|---------------|
| `brand` | Brand name |
| `product_name` | Product name |
| `product_url` | Link to the product |
| `product_id` | Nykaa product ID |
| `category` | Always "Lip Liner" |
| `price` | Selling price (₹) |
| `mrp` | Original price |
| `discount_percent` | Discount % |
| `rating` | Star rating (1–5) |
| `review_count` | Number of reviews |
| `stock_status` | In stock or not (product level) |
| `shade_name` | Shade name |
| `shade_id` | Shade ID |
| `shade_url` | Link to this shade |
| `shade_image` | Shade swatch image |
| `shade_availability` | In stock or not (shade level) |
| `shade_sku` | SKU code |

---

## Optional settings

You can change behaviour with environment variables:

| Setting | Default | What it does |
|---------|---------|--------------|
| `SCRAPER_ENV` | `dev` | Use `dev`, `test`, or `prod` |
| `HEADLESS` | `false` in dev | Hide the browser window (`true` / `false`) |
| `MAX_CONCURRENT_REQUESTS` | `5` | How many pages to fetch at once |
| `MIN_DELAY_SECONDS` | `0.5` | Shortest wait between requests |
| `MAX_DELAY_SECONDS` | `1.5` | Longest wait between requests |
| `MAX_RETRIES` | `4` | How many times to retry on failure |
| `PROXY` | none | Proxy URL if your IP is blocked |

Example:
```bash
SCRAPER_ENV=prod HEADLESS=true python scraper.py
```

---

## Project files

```
├── scraper.py          # Main script — run this
├── config.py           # Settings
├── nykaa_session.py    # Browser + HTTP setup
├── listing.py          # Fetches product list
├── shades.py           # Fetches shade details
├── models.py           # Data structure
├── io_utils.py         # Saves CSV/JSON and logs
├── output/             # Your results go here
└── logs/               # Run logs and failed URLs
```

---

## If something goes wrong

**"Access Denied" or HTTP 403**
- Nykaa blocks bots. Try running with the browser visible: `HEADLESS=false python scraper.py`
- Wait a few minutes and try again
- Use a proxy: `PROXY=http://your-proxy:port python scraper.py`

**Missing shades**
- Some products need extra browser loading. Check `logs/failed_urls.txt` for URLs that failed.

**Too slow**
- Use `--limit 5` to test first
- Don't set `MAX_CONCURRENT_REQUESTS` too high — Nykaa may block you

**Logs**
- `logs/scraper.log` — what happened during the run
- `logs/failed_urls.txt` — products that failed

---

## Git tip

Don't commit your virtual environment or output files. A pre-commit hook is included:

```bash
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## Disclaimer

For **learning and research only**. Please respect [Nykaa's Terms of Service](https://www.nykaa.com/terms-conditions/nc). Don't run this too aggressively — use reasonable delays between requests..

"""Main orchestrator for the Nykaa lip liner scraper."""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time
from typing import Any

from config import (
    CATEGORY_URL,
    LISTING_API_URL,
    MAX_CONCURRENT_REQUESTS,
    MAX_DELAY_SECONDS,
    MIN_DELAY_SECONDS,
)
from io_utils import ensure_directories, log_failed_url, setup_logging, write_outputs
from listing import discover_products
from models import Product, ShadeRow, flatten_product_shades
from nykaa_session import NykaaSession
from shades import extract_shades

logger = logging.getLogger("nykaa_scraper")


async def _jitter_delay() -> None:
    await asyncio.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))


async def _process_product(
    session: NykaaSession,
    product: Product,
    semaphore: asyncio.Semaphore,
) -> list[ShadeRow]:
    async with semaphore:
        await _jitter_delay()
        try:
            shades = await extract_shades(session, product)
            return flatten_product_shades(product, shades)
        except Exception as exc:
            logger.error("Error processing product %s: %s", product.product_id, exc)
            log_failed_url(product.product_url, str(exc))
            return flatten_product_shades(product, [])


async def run_scraper(limit: int | None = None) -> dict[str, Any]:
    ensure_directories()
    start = time.perf_counter()
    session = NykaaSession()
    all_rows: list[ShadeRow] = []
    runtime_stats: dict[str, Any] = {
        "category_url": CATEGORY_URL,
        "listing_api": LISTING_API_URL,
        "products_discovered": 0,
        "products_scraped": 0,
        "total_shades": 0,
        "failed_products": 0,
        "approach": "hybrid_api_with_playwright_session",
    }

    try:
        await session.bootstrap()
        products, listing_stats = await discover_products(session)
        runtime_stats.update(listing_stats)
        runtime_stats["products_discovered"] = len(products)

        if limit:
            products = products[:limit]
            logger.info("Limiting run to first %d products", limit)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        tasks = [_process_product(session, product, semaphore) for product in products]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for product, result in zip(products, results):
            if isinstance(result, Exception):
                runtime_stats["failed_products"] += 1
                log_failed_url(product.product_url, str(result))
                all_rows.extend(flatten_product_shades(product, []))
            else:
                runtime_stats["products_scraped"] += 1
                all_rows.extend(result)

        all_rows = _dedupe_rows(all_rows)
        runtime_stats["total_shades"] = len(all_rows)

        csv_path, json_path = write_outputs(all_rows)
        runtime_stats["csv_output"] = str(csv_path)
        runtime_stats["json_output"] = str(json_path)
        runtime_stats["elapsed_seconds"] = round(time.perf_counter() - start, 2)

        logger.info("=== Scrape Complete ===")
        logger.info("Products discovered: %d", runtime_stats["products_discovered"])
        logger.info("Products scraped: %d", runtime_stats["products_scraped"])
        logger.info("Total shade rows: %d", runtime_stats["total_shades"])
        logger.info("Failed products: %d", runtime_stats["failed_products"])
        logger.info("Runtime: %.2fs", runtime_stats["elapsed_seconds"])
        logger.info("CSV: %s", csv_path)
        logger.info("JSON: %s", json_path)

        return runtime_stats
    finally:
        await session.close()


def _dedupe_rows(rows: list[ShadeRow]) -> list[ShadeRow]:
    seen: set[tuple[str, str]] = set()
    unique: list[ShadeRow] = []
    for row in rows:
        key = (row.product_id, row.shade_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="Nykaa lip liner scraper")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of products (useful for dev/test runs)",
    )
    args = parser.parse_args()

    setup_logging()
    asyncio.run(run_scraper(limit=args.limit))


if __name__ == "__main__":
    main()

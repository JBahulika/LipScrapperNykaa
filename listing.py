"""Category listing discovery via Nykaa JSON API."""

from __future__ import annotations

import logging
import math
from typing import Any

from config import CATEGORY_NAME, LISTING_API_PARAMS, LISTING_API_URL
from io_utils import save_raw_response
from models import Product, product_from_listing
from nykaa_session import NykaaSession

logger = logging.getLogger("nykaa_scraper system")


async def discover_products(session: NykaaSession) -> tuple[list[Product], dict[str, Any]]:
    """Paginate listing API until all products are collected."""
    all_products: dict[str, Product] = {}
    stats: dict[str, Any] = {
        "api_endpoint": LISTING_API_URL,
        "pages_fetched": 0,
        "total_found": 0,
        "products_collected": 0,
    }

    page_no = 1
    total_found = None
    page_size = 20

    while True:
        params = {**LISTING_API_PARAMS, "page_no": str(page_no)}
        logger.info("Fetching listing page %d", page_no)
        payload = await session.get_json(LISTING_API_URL, params=params)

        if page_no == 1:
            save_raw_response("listing_page_1", payload)

        response = payload.get("response") or {}
        if total_found is None:
            total_found = int(response.get("total_found") or 0)
            stats["total_found"] = total_found
            logger.info("Category reports %d total products", total_found)

        products_raw = response.get("products") or []
        if not products_raw:
            logger.info("No products on page %d — stopping pagination", page_no)
            break

        for raw in products_raw:
            product = product_from_listing(raw, CATEGORY_NAME)
            if product.product_id:
                all_products[product.product_id] = product

        stats["pages_fetched"] = page_no
        stats["products_collected"] = len(all_products)

        offset = int(response.get("offset") or (page_no - 1) * page_size)
        if total_found and offset + len(products_raw) >= total_found:
            break
        if response.get("stop_further_call"):
            break
        if len(products_raw) < page_size:
            break

        page_no += 1
        if total_found and page_no > math.ceil(total_found / page_size) + 1:
            break

    products = list(all_products.values())
    logger.info(
        "Discovered %d unique products across %d pages",
        len(products),
        stats["pages_fetched"],
    )
    return products, stats

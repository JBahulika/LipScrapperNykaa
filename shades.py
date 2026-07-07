"""Shade extraction from PDP embedded JSON with Playwright fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import NYKAA_BASE_URL
from io_utils import log_failed_url, save_raw_response
from models import Product, Shade
from nykaa_session import NykaaSession

logger = logging.getLogger("nykaa_scraper")

PRELOADED_STATE_PATTERN = re.compile(
    r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>",
    re.DOTALL,
)
PRELOADED_STATE_ALT = re.compile(
    r"window\.__PRELOADED_STATE__\s*=\s*(\{.*)",
    re.DOTALL,
)

CHILD_KEYS = (
    "childProducts",
    "child_products",
    "children",
    "variants",
    "options",
    "shades",
    "shadeOptions",
    "shade_options",
    "productOptions",
)


async def extract_shades(session: NykaaSession, product: Product) -> list[Shade]:
    """Return shade variants for a product."""
    if product.product_type != "configurable" and product.option_count <= 1:
        return []

    url = product.product_url
    if not url:
        log_failed_url(str(product.product_id), "missing product_url")
        return []

    try:
        html = await session.get_text(url)
        state = _extract_preloaded_state(html)
        if state:
            shades = _shades_from_state(state, product)
            if shades:
                return shades

        logger.warning("Embedded state missing shades for %s — browser fallback", product.product_id)
        html = await session.browser_fetch_text(url)
        state = _extract_preloaded_state(html)
        if state:
            save_raw_response(f"pdp_{product.product_id}", state)
            shades = _shades_from_state(state, product)
            if shades:
                return shades

        shades = _shades_from_dom_fallback(html, product)
        if shades:
            return shades

    except Exception as exc:
        logger.error("Failed to extract shades for %s: %s", product.product_id, exc)
        log_failed_url(url, str(exc))

    return []


def _extract_preloaded_state(html: str) -> dict[str, Any] | None:
    match = PRELOADED_STATE_PATTERN.search(html)
    if not match:
        match = PRELOADED_STATE_ALT.search(html)
    if not match:
        return None

    raw = match.group(1).strip()
    if raw.endswith(";"):
        raw = raw[:-1]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        trimmed = _balance_json_object(raw)
        if trimmed:
            try:
                return json.loads(trimmed)
            except json.JSONDecodeError:
                return None
    return None


def _balance_json_object(raw: str) -> str | None:
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(raw):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[: index + 1]
    return None


def _shades_from_state(state: dict[str, Any], product: Product) -> list[Shade]:
    candidates = _find_child_product_lists(state)
    shades: list[Shade] = []
    seen: set[str] = set()

    for item in candidates:
        shade = _map_child_to_shade(item, product)
        if shade and shade.shade_id not in seen:
            seen.add(shade.shade_id)
            shades.append(shade)

    return shades


def _find_child_product_lists(node: Any, found: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if found is None:
        found = []

    if isinstance(node, dict):
        for key, value in node.items():
            if key in CHILD_KEYS and isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and _looks_like_shade(entry):
                        found.append(entry)
            elif isinstance(value, (dict, list)):
                _find_child_product_lists(value, found)
    elif isinstance(node, list):
        for item in node:
            _find_child_product_lists(item, found)

    return found


def _looks_like_shade(entry: dict[str, Any]) -> bool:
    has_id = any(k in entry for k in ("id", "product_id", "childId", "child_id"))
    has_name = any(
        k in entry
        for k in ("name", "shade_name", "option_name", "title", "shadeName", "variantName")
    )
    return has_id and has_name


def _map_child_to_shade(raw: dict[str, Any], product: Product) -> Shade | None:
    shade_id = str(
        raw.get("childId")
        or raw.get("id")
        or raw.get("product_id")
        or raw.get("child_id")
        or ""
    )
    if not shade_id:
        return None

    shade_name = (
        raw.get("variantName")
        or raw.get("name")
        or raw.get("shade_name")
        or raw.get("option_name")
        or raw.get("title")
        or raw.get("shadeName")
        or ""
    )

    slug = raw.get("slug") or raw.get("product_slug") or ""
    if slug and "/p/" in slug:
        base_slug = slug.rsplit("/p/", 1)[0]
        shade_url = f"{NYKAA_BASE_URL}/{base_slug.lstrip('/')}/p/{shade_id}"
    elif slug:
        shade_url = f"{NYKAA_BASE_URL}/{slug.lstrip('/')}"
    elif product.product_url and "/p/" in product.product_url:
        base_slug = product.product_url.replace(NYKAA_BASE_URL + "/", "").rsplit("/p/", 1)[0]
        shade_url = f"{NYKAA_BASE_URL}/{base_slug}/p/{shade_id}"
    else:
        shade_url = f"{NYKAA_BASE_URL}/p/{shade_id}"

    image = (
        raw.get("shadeImage")
        or raw.get("imageUrl")
        or raw.get("image_url")
        or raw.get("new_image_url")
        or raw.get("shade_image")
        or raw.get("image")
    )
    if not image:
        media = raw.get("media") or raw.get("carousel") or []
        if media and isinstance(media[0], dict):
            image = media[0].get("url")

    availability = _shade_availability(raw)
    sku = raw.get("sku") or raw.get("psku") or raw.get("d_sku")

    return Shade(
        shade_name=str(shade_name),
        shade_id=shade_id,
        shade_url=str(shade_url),
        shade_image=image,
        shade_availability=availability,
        shade_sku=sku,
        shade_price=_to_float(raw.get("offerPrice") or raw.get("final_price") or raw.get("price")),
        shade_mrp=_to_float(raw.get("mrp") or raw.get("price")),
    )


def _shade_availability(raw: dict[str, Any]) -> str:
    if raw.get("inStock") is False or raw.get("is_saleable") is False:
        return "out_of_stock"
    if raw.get("inStock") is True:
        return "in_stock"
    quantity = raw.get("quantity")
    if quantity is not None and int(quantity) <= 0:
        return "out_of_stock"
    if raw.get("in_stock") is False or raw.get("gludo_stock") is False:
        return "out_of_stock"
    if raw.get("in_stock") is True or raw.get("gludo_stock") is True:
        return "in_stock"
    return "unknown"


def _shades_from_dom_fallback(html: str, product: Product) -> list[Shade]:
    """Best-effort extraction from shade names embedded in PDP HTML."""
    pattern = re.compile(r"Select SHADE \(\d+\)\s*([^<]+)")
    match = pattern.search(html)
    if not match:
        return []

    names = re.findall(r"[A-Za-z][A-Za-z0-9\s'\-]+", match.group(1))
    shades: list[Shade] = []
    for name in names:
        cleaned = name.strip()
        if len(cleaned) < 2:
            continue
        shades.append(
            Shade(
                shade_name=cleaned,
                shade_id=product.product_id,
                shade_url=product.product_url,
                shade_image=product.image_url,
                shade_availability=product.stock_status,
                shade_sku=product.sku,
            )
        )
    return shades


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

"""Data models and row flattening for Nykaa lip liner products."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Product:
    product_id: str
    product_name: str
    brand: str
    product_url: str
    category: str
    price: float | None
    mrp: float | None
    discount_percent: float | None
    rating: float | None
    review_count: int | None
    stock_status: str
    product_type: str
    option_count: int
    sku: str | None = None
    image_url: str | None = None


@dataclass
class Shade:
    shade_name: str
    shade_id: str
    shade_url: str
    shade_image: str | None
    shade_availability: str
    shade_sku: str | None = None
    shade_price: float | None = None
    shade_mrp: float | None = None


@dataclass
class ShadeRow:
    brand: str
    product_name: str
    product_url: str
    product_id: str
    category: str
    price: float | None
    mrp: float | None
    discount_percent: float | None
    rating: float | None
    review_count: int | None
    stock_status: str
    shade_name: str
    shade_id: str
    shade_url: str
    shade_image: str | None
    shade_availability: str
    shade_sku: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CSV_COLUMNS = [
    "brand",
    "product_name",
    "product_url",
    "product_id",
    "category",
    "price",
    "mrp",
    "discount_percent",
    "rating",
    "review_count",
    "stock_status",
    "shade_name",
    "shade_id",
    "shade_url",
    "shade_image",
    "shade_availability",
    "shade_sku",
]


def _derive_stock_status(raw: dict[str, Any]) -> str:
    if raw.get("is_saleable") is False:
        return "out_of_stock"
    quantity = raw.get("quantity")
    if quantity is not None and int(quantity) <= 0:
        return "out_of_stock"
    if raw.get("gludo_stock") is False:
        return "out_of_stock"
    return "in_stock"


def product_from_listing(raw: dict[str, Any], category_fallback: str) -> Product:
    primary = raw.get("primary_categories") or {}
    l3 = primary.get("l3") or {}
    category = l3.get("name") or category_fallback

    return Product(
        product_id=str(raw.get("id", "")),
        product_name=raw.get("name") or raw.get("product_title") or "",
        brand=raw.get("brand_name") or "",
        product_url=raw.get("product_url") or "",
        category=category,
        price=_to_float(raw.get("final_price")),
        mrp=_to_float(raw.get("price")),
        discount_percent=_to_float(raw.get("discount")),
        rating=_to_float(raw.get("rating")),
        review_count=_to_int(raw.get("rating_count")),
        stock_status=_derive_stock_status(raw),
        product_type=raw.get("type") or "simple",
        option_count=int(raw.get("option_count") or 1),
        sku=raw.get("sku") or raw.get("psku"),
        image_url=raw.get("image_url") or raw.get("new_image_url"),
    )


def flatten_product_shades(product: Product, shades: list[Shade]) -> list[ShadeRow]:
    if not shades:
        shades = [_default_shade_from_product(product)]

    rows: list[ShadeRow] = []
    for shade in shades:
        price = shade.shade_price if shade.shade_price is not None else product.price
        mrp = shade.shade_mrp if shade.shade_mrp is not None else product.mrp
        discount = product.discount_percent
        if price is not None and mrp is not None and mrp > 0:
            discount = round((1 - price / mrp) * 100, 1)

        rows.append(
            ShadeRow(
                brand=product.brand,
                product_name=product.product_name,
                product_url=product.product_url,
                product_id=product.product_id,
                category=product.category,
                price=price,
                mrp=mrp,
                discount_percent=discount,
                rating=product.rating,
                review_count=product.review_count,
                stock_status=product.stock_status,
                shade_name=shade.shade_name,
                shade_id=shade.shade_id,
                shade_url=shade.shade_url,
                shade_image=shade.shade_image,
                shade_availability=shade.shade_availability,
                shade_sku=shade.shade_sku,
            )
        )
    return rows


def _default_shade_from_product(product: Product) -> Shade:
    return Shade(
        shade_name=product.product_name,
        shade_id=product.product_id,
        shade_url=product.product_url,
        shade_image=product.image_url,
        shade_availability=product.stock_status,
        shade_sku=product.sku,
        shade_price=product.price,
        shade_mrp=product.mrp,
    )


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

"""Logging, raw response persistence, and output writers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from config import (
    CSV_OUTPUT,
    FAILED_URLS_FILE,
    JSON_OUTPUT,
    LOG_FILE,
    LOGS_DIR,
    OUTPUT_DIR,
    RAW_API_DIR,
)
from models import CSV_COLUMNS, ShadeRow


def ensure_directories() -> None:
    for path in (OUTPUT_DIR, LOGS_DIR, RAW_API_DIR):
        path.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    ensure_directories()
    logger = logging.getLogger("nykaa_scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def log_failed_url(url: str, reason: str) -> None:
    ensure_directories()
    timestamp = datetime.now(timezone.utc).isoformat()
    with FAILED_URLS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp}\t{url}\t{reason}\n")


def save_raw_response(name: str, payload: Any) -> Path:
    ensure_directories()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = RAW_API_DIR / f"{name}_{timestamp}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def write_outputs(rows: list[ShadeRow]) -> tuple[Path, Path]:
    ensure_directories()
    data = [row.to_dict() for row in rows]
    frame = pd.DataFrame(data, columns=CSV_COLUMNS)
    frame.to_csv(CSV_OUTPUT, index=False)
    frame.to_json(JSON_OUTPUT, orient="records", indent=2, force_ascii=False)
    return CSV_OUTPUT, JSON_OUTPUT

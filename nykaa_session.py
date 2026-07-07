"""Playwright session bootstrap and HTTP client with harvested cookies."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import (
    AKAMAI_WAIT_SECONDS,
    BROWSER_TIMEOUT_MS,
    CATEGORY_URL,
    DEFAULT_HEADERS,
    HEADLESS,
    LISTING_API_PARAMS,
    LISTING_API_URL,
    MAX_RETRIES,
    NYKAA_BASE_URL,
    PROXY,
    REQUEST_TIMEOUT,
    RETRY_MAX_WAIT,
    RETRY_MIN_WAIT,
)

logger = logging.getLogger("nykaa_scraper")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class NykaaSession:
    """Manages Playwright browser context and HTTP clients sharing cookies."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._client: httpx.AsyncClient | None = None
        self.user_agent: str = DEFAULT_USER_AGENT
        self._use_playwright_transport = False

    async def bootstrap(self) -> None:
        logger.info("Bootstrapping Playwright session for Akamai bypass")
        self._playwright = await async_playwright().start()

        launch_kwargs: dict[str, Any] = {
            "headless": HEADLESS,
            "args": [
                "--disable-http2",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if PROXY:
            launch_kwargs["proxy"] = {"server": PROXY}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            locale="en-IN",
            viewport={"width": 1366, "height": 768},
            user_agent=DEFAULT_USER_AGENT,
            extra_http_headers=DEFAULT_HEADERS,
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(BROWSER_TIMEOUT_MS)

        await self._warm_up_session()
        cookies = await self._context.cookies()
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

        headers = {
            **DEFAULT_HEADERS,
            "User-Agent": self.user_agent,
            "Cookie": cookie_header,
        }

        client_kwargs: dict[str, Any] = {
            "headers": headers,
            "timeout": REQUEST_TIMEOUT,
            "follow_redirects": True,
        }
        if PROXY:
            client_kwargs["proxy"] = PROXY

        self._client = httpx.AsyncClient(**client_kwargs)

        if await self._verify_listing_access():
            logger.info("httpx transport verified — session ready with %d cookies", len(cookies))
        else:
            self._use_playwright_transport = True
            logger.warning(
                "httpx blocked — using Playwright request transport (%d cookies)",
                len(cookies),
            )

    async def _warm_up_session(self) -> None:
        """Seed Akamai cookies via lightweight requests before full navigation."""
        assert self._context is not None

        warmup_urls = [
            NYKAA_BASE_URL,
            CATEGORY_URL,
        ]
        for url in warmup_urls:
            try:
                response = await self._context.request.get(url, timeout=REQUEST_TIMEOUT * 1000)
                logger.info("Warmup %s -> HTTP %s", url, response.status)
            except Exception as exc:
                logger.warning("Warmup request failed for %s: %s", url, exc)

        await asyncio.sleep(AKAMAI_WAIT_SECONDS)

        try:
            await self._page.goto(
                CATEGORY_URL,
                wait_until="commit",
                timeout=min(BROWSER_TIMEOUT_MS, 30000),
            )
            self.user_agent = await self._page.evaluate("() => navigator.userAgent")
        except Exception as exc:
            logger.warning("Page navigation skipped (%s) — continuing with request cookies", exc)

    async def _verify_listing_access(self) -> bool:
        assert self._client is not None
        params = {**LISTING_API_PARAMS, "page_no": "1"}
        try:
            response = await self._client.get(LISTING_API_URL, params=params)
            if response.status_code == 200:
                payload = response.json()
                return payload.get("status") == "success"
        except Exception as exc:
            logger.warning("Listing verification via httpx failed: %s", exc)
        return False

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Session not bootstrapped. Call bootstrap() first.")
        return self._client

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Session not bootstrapped. Call bootstrap() first.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("Session not bootstrapped. Call bootstrap() first.")
        return self._context

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        reraise=True,
    )
    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._use_playwright_transport:
            return await self._playwright_get_json(url, params)

        response = await self.client.get(url, params=params)
        if response.status_code == 403:
            logger.warning("403 on %s — switching to Playwright transport", url)
            self._use_playwright_transport = True
            return await self._playwright_get_json(url, params)
        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        reraise=True,
    )
    async def get_text(self, url: str) -> str:
        if self._use_playwright_transport:
            return await self._playwright_get_text(url)

        response = await self.client.get(url)
        if response.status_code == 403:
            logger.warning("403 on %s — switching to Playwright transport", url)
            self._use_playwright_transport = True
            return await self._playwright_get_text(url)
        response.raise_for_status()
        return response.text

    async def _playwright_get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        text = await self._playwright_get_text(url, params)
        return json.loads(text)

    async def _playwright_get_text(
        self, url: str, params: dict[str, Any] | None = None
    ) -> str:
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{query}"
        else:
            full_url = url

        response = await self.context.request.get(full_url, timeout=REQUEST_TIMEOUT * 1000)
        if response.ok:
            return await response.text()

        if response.status == 403:
            return await self.browser_fetch_text(full_url)

        body = await response.text()
        raise RuntimeError(f"HTTP {response.status} for {full_url}: {body[:200]}")

    async def browser_fetch_text(self, url: str) -> str:
        response = None
        try:
            response = await self.context.request.get(url, timeout=REQUEST_TIMEOUT * 1000)
            if response.ok:
                body = await response.text()
                if body and "Access Denied" not in body[:500]:
                    return body
        except Exception as exc:
            logger.warning("Playwright request fetch failed for %s: %s", url, exc)

        try:
            await self.page.goto(url, wait_until="commit", timeout=min(BROWSER_TIMEOUT_MS, 45000))
            await asyncio.sleep(2)
            return await self.page.content()
        except Exception as exc:
            logger.error("Browser fetch failed for %s: %s", url, exc)
            if response is not None:
                return await response.text()
            raise

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Session closed")

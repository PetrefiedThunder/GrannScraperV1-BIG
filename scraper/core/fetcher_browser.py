"""
Browser-based fetcher using Playwright.

Handles JavaScript-heavy sites, SPAs, and infinite scroll.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from scraper.config.models import ScrapeJob, PaginationMode

logger = logging.getLogger(__name__)


class BrowserFetcher:
    """
    Playwright-based browser automation for JavaScript-heavy sites.

    Supports:
    - Headless/headful browsing
    - Wait for selectors
    - Infinite scroll
    - Screenshot capture
    - Network interception
    """

    def __init__(self, job: ScrapeJob):
        """
        Initialize browser fetcher.

        Args:
            job: ScrapeJob configuration
        """
        self.job = job
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self) -> "BrowserFetcher":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Initialize browser and context."""
        self.playwright = await async_playwright().start()

        # Launch browser
        browser_config = self.job.browser
        launch_options = {
            "headless": browser_config.headless,
        }

        # Add proxy if configured
        if self.job.proxy.enabled and self.job.proxy.proxy_list:
            proxy_url = self.job.proxy.proxy_list[0]  # Use first proxy
            launch_options["proxy"] = {"server": proxy_url}

        self.browser = await self.playwright.chromium.launch(**launch_options)

        # Create context
        context_options = {
            "viewport": {
                "width": browser_config.viewport_width,
                "height": browser_config.viewport_height,
            },
            "user_agent": browser_config.user_agent or None,
            "java_script_enabled": browser_config.javascript_enabled,
        }

        self.context = await self.browser.new_context(**context_options)

        # Set cookies if provided
        if self.job.cookies:
            cookies = [
                {"name": name, "value": value, "url": self.job.start_url}
                for name, value in self.job.cookies.items()
            ]
            await self.context.add_cookies(cookies)

        # Create page
        self.page = await self.context.new_page()

        # Set up resource blocking if configured
        if browser_config.block_images or browser_config.block_css:
            await self.page.route("**/*", self._handle_route)

        logger.info("Browser fetcher initialized")

    async def _handle_route(self, route: Any) -> None:
        """
        Handle route interception for resource blocking.

        Args:
            route: Playwright route object
        """
        resource_type = route.request.resource_type
        block = False

        if self.job.browser.block_images and resource_type == "image":
            block = True
        if self.job.browser.block_css and resource_type == "stylesheet":
            block = True

        if block:
            await route.abort()
        else:
            await route.continue_()

    async def close(self) -> None:
        """Close browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("Browser fetcher closed")

    async def fetch(
        self, url: str, wait_for_selector: Optional[str] = None
    ) -> tuple[Optional[BeautifulSoup], Optional[str]]:
        """
        Fetch and parse a URL using browser.

        Args:
            url: URL to fetch
            wait_for_selector: Optional selector to wait for (overrides job config)

        Returns:
            Tuple of (parsed BeautifulSoup, raw HTML) or (None, None) on failure
        """
        if not self.page:
            raise RuntimeError("Browser not started. Use async with BrowserFetcher()...")

        try:
            logger.debug(f"Navigating to {url}")

            # Navigate to page
            await self.page.goto(
                url,
                timeout=self.job.browser.page_load_timeout,
                wait_until="domcontentloaded",
            )

            # Wait for specific selector if configured
            selector = wait_for_selector or self.job.browser.wait_for_selector
            if selector:
                logger.debug(f"Waiting for selector: {selector}")
                await self.page.wait_for_selector(
                    selector,
                    timeout=self.job.browser.wait_timeout,
                )

            # Handle infinite scroll if configured
            if self.job.pagination.mode == PaginationMode.INFINITE_SCROLL:
                await self._handle_infinite_scroll()

            # Get HTML content
            html = await self.page.content()
            soup = BeautifulSoup(html, "lxml")

            # Capture screenshot if configured
            if self.job.browser.capture_screenshot:
                await self._capture_screenshot(url)

            logger.info(f"Successfully fetched {url} ({len(html)} bytes)")
            return soup, html

        except Exception as e:
            logger.error(f"Browser error fetching {url}: {e}")
            return None, None

    async def _handle_infinite_scroll(self) -> None:
        """
        Handle infinite scroll pagination.

        Scrolls page multiple times with pauses to trigger lazy loading.
        """
        if not self.page:
            return

        scroll_times = self.job.pagination.scroll_times
        scroll_pause = self.job.pagination.scroll_pause

        logger.info(f"Handling infinite scroll ({scroll_times} scrolls)")

        for i in range(scroll_times):
            # Scroll to bottom
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            # Wait for content to load
            await asyncio.sleep(scroll_pause)

            logger.debug(f"Scroll {i + 1}/{scroll_times}")

        # Scroll back to top
        await self.page.evaluate("window.scrollTo(0, 0)")

    async def _capture_screenshot(self, url: str) -> None:
        """
        Capture screenshot of current page.

        Args:
            url: URL being captured (used for filename)
        """
        if not self.page or not self.job.browser.screenshot_path:
            return

        try:
            # Create screenshot directory
            screenshot_dir = Path(self.job.browser.screenshot_path)
            screenshot_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            filename = f"{parsed.netloc}_{parsed.path.replace('/', '_')}.png"
            filepath = screenshot_dir / filename

            # Capture screenshot
            await self.page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved to {filepath}")

        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")

    async def wait_for_navigation(self, timeout: Optional[int] = None) -> None:
        """
        Wait for navigation to complete.

        Args:
            timeout: Timeout in milliseconds (uses job config if not provided)
        """
        if not self.page:
            return

        timeout_ms = timeout or self.job.browser.page_load_timeout
        await self.page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)

    async def click_element(self, selector: str) -> bool:
        """
        Click an element by selector.

        Args:
            selector: CSS selector

        Returns:
            True if click succeeded
        """
        if not self.page:
            return False

        try:
            await self.page.click(selector, timeout=self.job.browser.wait_timeout)
            logger.debug(f"Clicked element: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Failed to click {selector}: {e}")
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        """
        Type text into an input field.

        Args:
            selector: CSS selector for input
            text: Text to type

        Returns:
            True if typing succeeded
        """
        if not self.page:
            return False

        try:
            await self.page.fill(selector, text, timeout=self.job.browser.wait_timeout)
            logger.debug(f"Typed into {selector}")
            return True
        except Exception as e:
            logger.warning(f"Failed to type into {selector}: {e}")
            return False

    async def execute_script(self, script: str) -> Any:
        """
        Execute JavaScript in page context.

        Args:
            script: JavaScript code to execute

        Returns:
            Script return value
        """
        if not self.page:
            return None

        try:
            result = await self.page.evaluate(script)
            return result
        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return None

    async def get_element_property(
        self, selector: str, property_name: str
    ) -> Optional[str]:
        """
        Get property value of an element.

        Args:
            selector: CSS selector
            property_name: Property name (e.g., 'textContent', 'href')

        Returns:
            Property value or None
        """
        if not self.page:
            return None

        try:
            element = await self.page.query_selector(selector)
            if not element:
                return None

            value = await element.get_property(property_name)
            return await value.json_value()
        except Exception as e:
            logger.warning(f"Failed to get property {property_name} from {selector}: {e}")
            return None

    async def wait_for_text(
        self, text: str, timeout: Optional[int] = None
    ) -> bool:
        """
        Wait for specific text to appear on page.

        Args:
            text: Text to wait for
            timeout: Timeout in milliseconds

        Returns:
            True if text appeared
        """
        if not self.page:
            return False

        try:
            timeout_ms = timeout or self.job.browser.wait_timeout
            await self.page.wait_for_selector(
                f"text={text}",
                timeout=timeout_ms,
            )
            return True
        except Exception as e:
            logger.warning(f"Text '{text}' did not appear: {e}")
            return False

"""
Static HTTP fetcher using httpx and BeautifulSoup.

Handles all non-JavaScript scraping with async HTTP requests.
"""

import asyncio
import logging
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from scraper.config.models import ScrapeJob, UserAgentStrategy

logger = logging.getLogger(__name__)


class StaticFetcher:
    """
    High-performance static HTML fetcher.

    Uses httpx for async HTTP requests and BeautifulSoup for parsing.
    Handles sessions, cookies, headers, and user agent rotation.
    """

    def __init__(self, job: ScrapeJob):
        """
        Initialize fetcher with job configuration.

        Args:
            job: ScrapeJob configuration
        """
        self.job = job
        self.ua = UserAgent()
        self.session: Optional[httpx.AsyncClient] = None
        self._current_proxy_index = 0
        self._user_agent_index = 0

    async def __aenter__(self) -> "StaticFetcher":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Initialize HTTP session."""
        # Build headers
        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        headers.update(self.job.custom_headers)

        # Configure session
        self.session = httpx.AsyncClient(
            headers=headers,
            cookies=self.job.cookies,
            timeout=httpx.Timeout(self.job.retry.timeout),
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=self.job.rate_limit.max_concurrent_requests,
                max_connections=self.job.rate_limit.max_concurrent_requests * 2,
            ),
        )

        logger.info("Static fetcher initialized")

    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.aclose()
            logger.info("Static fetcher closed")

    def _get_user_agent(self) -> str:
        """
        Get user agent based on strategy.

        Returns:
            User agent string
        """
        strategy = self.job.user_agent_strategy

        if strategy == UserAgentStrategy.FIXED:
            if self.job.user_agent_list:
                return self.job.user_agent_list[0]
            return self.ua.chrome

        elif strategy == UserAgentStrategy.ROTATING_LIST:
            if not self.job.user_agent_list:
                return self.ua.random
            ua = self.job.user_agent_list[self._user_agent_index]
            self._user_agent_index = (
                self._user_agent_index + 1
            ) % len(self.job.user_agent_list)
            return ua

        else:  # RANDOM
            return self.ua.random

    def _get_proxy(self) -> Optional[dict[str, str]]:
        """
        Get next proxy from pool using rotation strategy.

        Returns:
            Proxy dict for httpx, or None
        """
        if not self.job.proxy.enabled or not self.job.proxy.proxy_list:
            return None

        strategy = self.job.proxy.rotation_strategy
        proxies = self.job.proxy.proxy_list

        if strategy == "round_robin":
            proxy = proxies[self._current_proxy_index]
            self._current_proxy_index = (self._current_proxy_index + 1) % len(proxies)
        elif strategy == "random":
            import random
            proxy = random.choice(proxies)
        else:  # least_used - simplified to round_robin for now
            proxy = proxies[self._current_proxy_index]
            self._current_proxy_index = (self._current_proxy_index + 1) % len(proxies)

        return {"http://": proxy, "https://": proxy}

    async def fetch(
        self, url: str, retry_count: int = 0
    ) -> tuple[Optional[BeautifulSoup], Optional[str]]:
        """
        Fetch and parse a URL.

        Args:
            url: URL to fetch
            retry_count: Current retry attempt

        Returns:
            Tuple of (parsed BeautifulSoup, raw HTML) or (None, None) on failure
        """
        if not self.session:
            raise RuntimeError("Fetcher not started. Use async with StaticFetcher()...")

        try:
            # Update user agent if rotating
            if self.job.user_agent_strategy == UserAgentStrategy.RANDOM:
                self.session.headers["User-Agent"] = self._get_user_agent()

            # Get proxy if configured
            proxy = self._get_proxy()
            request_kwargs: dict[str, Any] = {}
            if proxy:
                request_kwargs["proxies"] = proxy

            logger.debug(f"Fetching {url}")

            # Make request
            response = await self.session.get(url, **request_kwargs)
            response.raise_for_status()

            # Parse HTML
            html = response.text
            soup = BeautifulSoup(html, "lxml")

            logger.info(f"Successfully fetched {url} ({len(html)} bytes)")
            return soup, html

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.warning(f"HTTP {status_code} for {url}")

            # Retry on configured status codes
            if (
                status_code in self.job.retry.retry_on_status
                and retry_count < self.job.retry.max_retries
            ):
                backoff = self.job.retry.backoff_factor ** retry_count
                logger.info(f"Retrying in {backoff}s (attempt {retry_count + 1})")
                await asyncio.sleep(backoff)
                return await self.fetch(url, retry_count + 1)

            return None, None

        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")

            # Retry on network errors
            if retry_count < self.job.retry.max_retries:
                backoff = self.job.retry.backoff_factor ** retry_count
                logger.info(f"Retrying in {backoff}s (attempt {retry_count + 1})")
                await asyncio.sleep(backoff)
                return await self.fetch(url, retry_count + 1)

            return None, None

        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None, None

    async def fetch_multiple(
        self, urls: list[str], max_concurrent: Optional[int] = None
    ) -> list[tuple[str, Optional[BeautifulSoup], Optional[str]]]:
        """
        Fetch multiple URLs concurrently with rate limiting.

        Args:
            urls: List of URLs to fetch
            max_concurrent: Max concurrent requests (overrides job config)

        Returns:
            List of tuples (url, soup, html)
        """
        if max_concurrent is None:
            max_concurrent = self.job.rate_limit.max_concurrent_requests

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(url: str) -> tuple[str, Optional[BeautifulSoup], Optional[str]]:
            async with semaphore:
                soup, html = await self.fetch(url)
                # Respect rate limiting delay
                delay = self.job.rate_limit.min_delay
                if self.job.rate_limit.max_delay > self.job.rate_limit.min_delay:
                    import random
                    delay = random.uniform(
                        self.job.rate_limit.min_delay,
                        self.job.rate_limit.max_delay
                    )
                await asyncio.sleep(delay)
                return url, soup, html

        results = await asyncio.gather(
            *[fetch_with_semaphore(url) for url in urls],
            return_exceptions=True
        )

        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in concurrent fetch: {result}")
                continue
            valid_results.append(result)

        return valid_results

    def is_same_domain(self, url: str) -> bool:
        """
        Check if URL is in allowed domains.

        Args:
            url: URL to check

        Returns:
            True if URL is allowed
        """
        if not self.job.allowed_domains:
            return True

        domain = urlparse(url).netloc
        return any(
            domain == allowed or domain.endswith(f".{allowed}")
            for allowed in self.job.allowed_domains
        )

    def resolve_url(self, url: str, base_url: str) -> str:
        """
        Resolve relative URL to absolute.

        Args:
            url: URL to resolve (may be relative)
            base_url: Base URL for resolution

        Returns:
            Absolute URL
        """
        return urljoin(base_url, url)

    async def check_robots_txt(self, url: str) -> bool:
        """
        Check if URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed
        """
        if not self.job.rate_limit.respect_robots_txt:
            return True

        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            soup, robots_txt = await self.fetch(robots_url)
            if not robots_txt:
                # No robots.txt = allowed
                return True

            # Simple robots.txt parsing (could use robotparser for more sophistication)
            user_agent = self.session.headers.get("User-Agent", "*") if self.session else "*"
            disallowed = []
            current_ua = None

            for line in robots_txt.split("\n"):
                line = line.split("#")[0].strip()  # Remove comments
                if not line:
                    continue

                if line.lower().startswith("user-agent:"):
                    current_ua = line.split(":", 1)[1].strip()
                elif line.lower().startswith("disallow:"):
                    if current_ua == "*" or user_agent.startswith(current_ua):
                        path = line.split(":", 1)[1].strip()
                        if path:
                            disallowed.append(path)

            # Check if current path is disallowed
            current_path = parsed.path or "/"
            for path in disallowed:
                if current_path.startswith(path):
                    logger.warning(f"URL {url} disallowed by robots.txt")
                    return False

            return True

        except Exception as e:
            logger.debug(f"Could not fetch robots.txt: {e}")
            # If we can't fetch robots.txt, allow the request
            return True

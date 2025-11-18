"""
Rate limiting and politeness engine.

Token bucket algorithm with domain-specific rate limiting.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

from scraper.config.models import RateLimitConfig

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with per-domain tracking.

    Ensures politeness by limiting requests per second per domain.
    """

    def __init__(self, config: RateLimitConfig):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.domain_buckets: dict[str, dict] = defaultdict(
            lambda: {
                "tokens": config.max_concurrent_requests,
                "last_update": time.time(),
                "max_tokens": config.max_concurrent_requests,
            }
        )
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)

    async def acquire(self, domain: str) -> None:
        """
        Acquire permission to make a request to domain.

        Args:
            domain: Domain being accessed
        """
        if not self.config.enabled:
            return

        # Global concurrency limit
        await self.semaphore.acquire()

        # Domain-specific rate limiting
        if self.config.requests_per_second:
            await self._wait_for_token(domain)

        # Random delay between min and max
        delay = self.config.min_delay
        if self.config.max_delay > self.config.min_delay:
            import random
            delay = random.uniform(self.config.min_delay, self.config.max_delay)

        await asyncio.sleep(delay)

    def release(self, domain: str) -> None:
        """
        Release rate limit for domain.

        Args:
            domain: Domain being released
        """
        if not self.config.enabled:
            return

        self.semaphore.release()

    async def _wait_for_token(self, domain: str) -> None:
        """
        Wait for token bucket to have available tokens.

        Args:
            domain: Domain to check
        """
        if not self.config.requests_per_second:
            return

        bucket = self.domain_buckets[domain]

        while True:
            now = time.time()
            time_passed = now - bucket["last_update"]

            # Refill tokens based on time passed
            refill_rate = self.config.requests_per_second
            tokens_to_add = time_passed * refill_rate
            bucket["tokens"] = min(
                bucket["max_tokens"],
                bucket["tokens"] + tokens_to_add
            )
            bucket["last_update"] = now

            # Check if we have a token
            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                break

            # Wait a bit before checking again
            wait_time = (1.0 - bucket["tokens"]) / refill_rate
            await asyncio.sleep(wait_time)

    async def __aenter__(self) -> "RateLimiter":
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        pass


class SessionManager:
    """
    Manages scraping sessions with persistent state.

    Tracks visited URLs, cookies, and session metadata.
    """

    def __init__(self):
        """Initialize session manager."""
        self.visited_urls: set[str] = set()
        self.failed_urls: set[str] = set()
        self.cookies: dict[str, str] = {}
        self.metadata: dict[str, any] = {}

    def mark_visited(self, url: str) -> None:
        """
        Mark URL as visited.

        Args:
            url: URL that was visited
        """
        self.visited_urls.add(url)

    def mark_failed(self, url: str) -> None:
        """
        Mark URL as failed.

        Args:
            url: URL that failed
        """
        self.failed_urls.add(url)

    def is_visited(self, url: str) -> bool:
        """
        Check if URL has been visited.

        Args:
            url: URL to check

        Returns:
            True if visited
        """
        return url in self.visited_urls

    def is_failed(self, url: str) -> bool:
        """
        Check if URL previously failed.

        Args:
            url: URL to check

        Returns:
            True if failed
        """
        return url in self.failed_urls

    def get_stats(self) -> dict[str, int]:
        """
        Get session statistics.

        Returns:
            Dict with visited, failed counts
        """
        return {
            "visited": len(self.visited_urls),
            "failed": len(self.failed_urls),
        }

    def update_cookies(self, new_cookies: dict[str, str]) -> None:
        """
        Update session cookies.

        Args:
            new_cookies: New cookies to merge
        """
        self.cookies.update(new_cookies)

    def reset(self) -> None:
        """Reset session state."""
        self.visited_urls.clear()
        self.failed_urls.clear()
        self.cookies.clear()
        self.metadata.clear()
        logger.info("Session reset")

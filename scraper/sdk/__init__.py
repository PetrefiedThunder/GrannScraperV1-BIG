"""
GrandmaScrape Python SDK.

Pythonic interface to the GrandmaScrape API.

Usage:
    from scraper.sdk import GrandmaScrapeClient

    # Synchronous client
    with GrandmaScrapeClient() as client:
        job_id = client.auto_scrape("https://example.com")
        results = client.get_all_results(job_id)

    # Async client
    async with AsyncGrandmaScrapeClient() as client:
        job_id = await client.auto_scrape("https://example.com")
        results = await client.get_all_results(job_id)
"""

from scraper.sdk.client import (
    GrandmaScrapeClient,
    AsyncGrandmaScrapeClient,
    JobStatus
)

__all__ = [
    'GrandmaScrapeClient',
    'AsyncGrandmaScrapeClient',
    'JobStatus'
]

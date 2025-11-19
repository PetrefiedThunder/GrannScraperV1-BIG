#!/usr/bin/env python3
"""
Example 3: Async Concurrent Scraping - Scrape multiple sites simultaneously

This example shows how to scrape multiple websites concurrently using async/await.
"""

import asyncio
from scraper.sdk import AsyncGrandmaScrapeClient


async def scrape_site(client, url, name):
    """Scrape a single site."""
    print(f"🚀 Starting: {name}")

    job_id = await client.auto_scrape(
        url=url,
        max_pages=3,
        concurrent=True,
        wait=False  # Don't wait yet - we'll wait for all together
    )

    # Wait for completion
    await client.wait_for_job(job_id)

    # Get results
    results = await client.get_all_results(job_id)

    print(f"✅ {name}: {len(results)} items scraped")
    return {
        'name': name,
        'url': url,
        'job_id': job_id,
        'count': len(results),
        'data': results
    }


async def main():
    print("⚡ Async Concurrent Scraping Example\n")

    # Sites to scrape (examples - use real sites)
    sites = [
        ("https://news.ycombinator.com", "Hacker News"),
        ("https://books.toscrape.com", "Books to Scrape"),
        ("https://quotes.toscrape.com", "Quotes to Scrape"),
    ]

    async with AsyncGrandmaScrapeClient() as client:
        print(f"Scraping {len(sites)} sites concurrently...\n")

        # Create tasks for concurrent scraping
        tasks = [
            scrape_site(client, url, name)
            for url, name in sites
        ]

        # Run all scrapes concurrently
        import time
        start_time = time.time()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time

        # Process results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)

        total_items = 0
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Error: {result}")
            else:
                print(f"\n{result['name']}:")
                print(f"  URL: {result['url']}")
                print(f"  Job ID: {result['job_id']}")
                print(f"  Items: {result['count']}")
                total_items += result['count']

        print("\n" + "=" * 60)
        print(f"✨ Total items scraped: {total_items}")
        print(f"⏱️  Total time: {elapsed:.2f}s")
        print(f"📊 Average time per site: {elapsed/len(sites):.2f}s")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

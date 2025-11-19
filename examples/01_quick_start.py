#!/usr/bin/env python3
"""
Example 1: Quick Start - Scrape a website in 5 lines of code

This example shows the simplest way to use GrandmaScrape.
"""

from scraper.sdk import GrandmaScrapeClient

def main():
    print("🧓 GrandmaScrape - Quick Start Example\n")

    # 1. Create client (assumes API server is running at localhost:8000)
    with GrandmaScrapeClient("http://localhost:8000") as client:

        # 2. Auto-scrape a website (AI-powered, zero config!)
        print("Starting auto-scrape...")
        job_id = client.auto_scrape(
            url="https://news.ycombinator.com",  # Example site
            max_pages=3,                          # Scrape 3 pages
            export_format="json",                 # Export as JSON
            concurrent=True,                      # Use concurrent scraping (10x faster)
            wait=True                             # Wait for completion
        )

        print(f"✅ Job completed! ID: {job_id}")

        # 3. Get results
        results = client.get_all_results(job_id)
        print(f"📊 Scraped {len(results)} items\n")

        # 4. Show first few results
        for i, item in enumerate(results[:5], 1):
            print(f"{i}. {item}")

        # 5. Check data quality
        quality = client.check_data_quality(job_id)
        score = quality['quality_report']['quality_score']
        print(f"\n✨ Data quality score: {score:.1%}")


if __name__ == "__main__":
    # Note: Make sure API server is running first:
    # python -m scraper.api.rest_server
    main()

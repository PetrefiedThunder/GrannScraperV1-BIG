#!/usr/bin/env python3
"""
Example 2: Pandas Integration - Scrape data and analyze with Pandas

This example shows how to integrate GrandmaScrape with Pandas for data analysis.
"""

import pandas as pd
from scraper.sdk import GrandmaScrapeClient


def main():
    print("🐼 GrandmaScrape + Pandas Integration\n")

    with GrandmaScrapeClient() as client:
        # Scrape e-commerce product data
        print("Scraping product data...")
        job_id = client.auto_scrape(
            url="https://books.toscrape.com",  # Example bookstore
            max_pages=5,
            concurrent=True,
            wait=True
        )

        # Get results as list of dicts
        results = client.get_all_results(job_id)
        print(f"✅ Scraped {len(results)} items")

        # Convert to Pandas DataFrame
        df = pd.DataFrame(results)
        print(f"\n📊 DataFrame shape: {df.shape}")
        print(f"Columns: {list(df.columns)}\n")

        # Data analysis examples
        print("=" * 60)
        print("DATA ANALYSIS")
        print("=" * 60)

        # 1. Basic statistics
        if 'price' in df.columns:
            print("\n💰 Price Statistics:")
            print(df['price'].describe())

        # 2. Missing data analysis
        print("\n🔍 Missing Data:")
        missing = df.isnull().sum()
        print(missing[missing > 0])

        # 3. Top categories (if available)
        if 'category' in df.columns:
            print("\n📚 Top Categories:")
            print(df['category'].value_counts().head(10))

        # 4. Data quality check
        quality = client.check_data_quality(job_id)
        print(f"\n✨ Data Quality Score: {quality['quality_report']['quality_score']:.1%}")

        # Export to various formats
        print("\n💾 Exporting data...")
        df.to_csv('scraped_data.csv', index=False)
        df.to_excel('scraped_data.xlsx', index=False)
        df.to_json('scraped_data.json', orient='records', indent=2)

        print("✅ Exported to:")
        print("   - scraped_data.csv")
        print("   - scraped_data.xlsx")
        print("   - scraped_data.json")

        # Advanced: Filter and transform
        print("\n🔧 Data Transformation Example:")
        if 'price' in df.columns:
            # Filter expensive items
            expensive = df[df['price'] > df['price'].median()]
            print(f"Items above median price: {len(expensive)}")

            # Create price categories
            df['price_category'] = pd.cut(
                df['price'],
                bins=[0, 10, 20, 50, float('inf')],
                labels=['Budget', 'Economy', 'Standard', 'Premium']
            )
            print("\nPrice Categories:")
            print(df['price_category'].value_counts())


if __name__ == "__main__":
    main()

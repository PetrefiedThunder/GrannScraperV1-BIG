#!/usr/bin/env python3
"""
Example 4: Workflow DAG - Complex multi-step scraping pipelines

This example shows how to create complex workflows with dependencies.
"""

import asyncio
from scraper.scheduler.workflow_dag import WorkflowBuilder


async def scrape_products(context):
    """Step 1: Scrape product listings."""
    print("📦 Step 1: Scraping products...")
    await asyncio.sleep(1)  # Simulate scraping
    products = [
        {"id": 1, "name": "Product A", "price": 19.99},
        {"id": 2, "name": "Product B", "price": 29.99},
        {"id": 3, "name": "Product C", "price": 39.99},
    ]
    print(f"   Found {len(products)} products")
    return {"products": products}


async def scrape_reviews(context):
    """Step 2: Scrape reviews for each product."""
    print("⭐ Step 2: Scraping reviews...")
    products = context.get('scrape_products', {}).get('products', [])
    await asyncio.sleep(1)  # Simulate scraping
    reviews = {}
    for product in products:
        reviews[product['id']] = [
            f"Great {product['name']}!",
            f"Love this product",
        ]
    print(f"   Found reviews for {len(reviews)} products")
    return {"reviews": reviews}


async def scrape_prices(context):
    """Step 2b: Scrape competitor prices (runs in parallel with reviews)."""
    print("💰 Step 2b: Scraping competitor prices...")
    products = context.get('scrape_products', {}).get('products', [])
    await asyncio.sleep(1)  # Simulate scraping
    competitor_prices = {}
    for product in products:
        competitor_prices[product['id']] = product['price'] * 0.9  # 10% cheaper
    print(f"   Found competitor prices for {len(competitor_prices)} products")
    return {"competitor_prices": competitor_prices}


async def analyze_data(context):
    """Step 3: Analyze all collected data."""
    print("📊 Step 3: Analyzing data...")
    products = context.get('scrape_products', {}).get('products', [])
    reviews = context.get('scrape_reviews', {}).get('reviews', {})
    competitor_prices = context.get('scrape_prices', {}).get('competitor_prices', {})

    await asyncio.sleep(1)  # Simulate analysis

    analysis = []
    for product in products:
        review_count = len(reviews.get(product['id'], []))
        our_price = product['price']
        comp_price = competitor_prices.get(product['id'], our_price)
        price_diff = our_price - comp_price

        analysis.append({
            'product': product['name'],
            'our_price': our_price,
            'competitor_price': comp_price,
            'price_difference': price_diff,
            'review_count': review_count,
            'competitive': price_diff <= 0,
        })

    print(f"   Analyzed {len(analysis)} products")
    return {"analysis": analysis}


async def export_report(context):
    """Step 4: Export final report."""
    print("💾 Step 4: Exporting report...")
    analysis = context.get('analyze_data', {}).get('analysis', [])

    await asyncio.sleep(0.5)  # Simulate export

    print("\n" + "=" * 60)
    print("COMPETITIVE ANALYSIS REPORT")
    print("=" * 60)

    for item in analysis:
        status = "✅ Competitive" if item['competitive'] else "⚠️ Overpriced"
        print(f"\n{item['product']} - {status}")
        print(f"  Our Price: ${item['our_price']:.2f}")
        print(f"  Competitor Price: ${item['competitor_price']:.2f}")
        print(f"  Difference: ${item['price_difference']:.2f}")
        print(f"  Reviews: {item['review_count']}")

    print("\n" + "=" * 60)
    print("✅ Report exported successfully")
    return {"status": "success"}


async def main():
    print("🔄 Workflow DAG Example\n")

    # Build workflow with dependencies
    workflow = (
        WorkflowBuilder("competitive_analysis")
        # Step 1: Scrape products (no dependencies)
        .add_node("scrape_products", scrape_products)

        # Step 2: Scrape reviews (depends on products)
        .add_node("scrape_reviews", scrape_reviews, depends_on=["scrape_products"])

        # Step 2b: Scrape prices (also depends on products, runs in parallel with reviews)
        .add_node("scrape_prices", scrape_prices, depends_on=["scrape_products"])

        # Step 3: Analyze (depends on all scraping steps)
        .add_node(
            "analyze_data",
            analyze_data,
            depends_on=["scrape_products", "scrape_reviews", "scrape_prices"]
        )

        # Step 4: Export (depends on analysis)
        .add_node("export_report", export_report, depends_on=["analyze_data"])

        .build()
    )

    # Visualize workflow
    print("Workflow structure:")
    print(workflow.visualize())
    print()

    # Execute workflow
    print("Executing workflow...\n")
    executor_map = {
        'scrape_products': scrape_products,
        'scrape_reviews': scrape_reviews,
        'scrape_prices': scrape_prices,
        'analyze_data': analyze_data,
        'export_report': export_report,
    }

    result = await workflow.execute(executor_map)

    if result['status'] == 'success':
        print("\n✨ Workflow completed successfully!")
    else:
        print(f"\n❌ Workflow failed: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())

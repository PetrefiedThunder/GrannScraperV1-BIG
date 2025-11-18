"""
Pytest configuration and fixtures.
"""

import pytest


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <div class="container">
            <article class="item">
                <h2 class="title">Item 1</h2>
                <p class="description">Description 1</p>
                <span class="price">$19.99</span>
                <a class="link" href="/item1">Link 1</a>
            </article>
            <article class="item">
                <h2 class="title">Item 2</h2>
                <p class="description">Description 2</p>
                <span class="price">$29.99</span>
                <a class="link" href="/item2">Link 2</a>
            </article>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_job_data():
    """Sample job configuration data."""
    return {
        "name": "test_job",
        "start_url": "https://example.com",
        "item_selector": ".item",
        "fields": {
            "title": {
                "selector": ".title",
                "type": "string",
            },
            "price": {
                "selector": ".price",
                "type": "currency",
            },
        },
        "pagination": {
            "mode": "none",
        },
        "export": {
            "formats": ["json"],
        },
    }

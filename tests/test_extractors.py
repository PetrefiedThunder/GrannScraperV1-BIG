"""
Tests for extractors.
"""

import pytest
from bs4 import BeautifulSoup

from scraper.config.models import FieldConfig, FieldType
from scraper.extractors.selector_extractor import SelectorExtractor, TableExtractor


@pytest.mark.asyncio
async def test_selector_extractor_text():
    """Test extracting text content."""
    html = """
    <div class="container">
        <h1 class="title">Test Title</h1>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")

    extractor = SelectorExtractor()
    field_config = FieldConfig(selector=".title", type=FieldType.STRING)

    result = await extractor.extract(soup, "title", field_config)

    assert result == "Test Title"


@pytest.mark.asyncio
async def test_selector_extractor_attribute():
    """Test extracting HTML attributes."""
    html = """
    <a class="link" href="https://example.com">Click</a>
    """
    soup = BeautifulSoup(html, "lxml")

    extractor = SelectorExtractor()
    field_config = FieldConfig(
        selector=".link",
        attr="href",
        type=FieldType.URL,
    )

    result = await extractor.extract(soup, "url", field_config)

    assert result == "https://example.com"


@pytest.mark.asyncio
async def test_selector_extractor_multiple():
    """Test extracting multiple values."""
    html = """
    <ul>
        <li class="item">Item 1</li>
        <li class="item">Item 2</li>
        <li class="item">Item 3</li>
    </ul>
    """
    soup = BeautifulSoup(html, "lxml")

    extractor = SelectorExtractor()
    field_config = FieldConfig(
        selector=".item",
        type=FieldType.STRING,
        multiple=True,
    )

    result = await extractor.extract(soup, "items", field_config)

    assert len(result) == 3
    assert "Item 1" in result
    assert "Item 3" in result


@pytest.mark.asyncio
async def test_selector_extractor_regex():
    """Test extracting with regex."""
    html = """
    <div class="price">Price: $99.99</div>
    """
    soup = BeautifulSoup(html, "lxml")

    extractor = SelectorExtractor()
    field_config = FieldConfig(
        selector=".price",
        type=FieldType.STRING,
        regex=r"\$(\d+\.\d+)",
    )

    result = await extractor.extract(soup, "price", field_config)

    assert result == "99.99"


@pytest.mark.asyncio
async def test_selector_extractor_default():
    """Test default value when selector not found."""
    html = "<div>No match</div>"
    soup = BeautifulSoup(html, "lxml")

    extractor = SelectorExtractor()
    field_config = FieldConfig(
        selector=".missing",
        type=FieldType.STRING,
        default="N/A",
    )

    result = await extractor.extract(soup, "field", field_config)

    assert result == "N/A"


@pytest.mark.asyncio
async def test_table_extractor():
    """Test table extraction."""
    html = """
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>Age</th>
                <th>City</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Alice</td>
                <td>30</td>
                <td>NYC</td>
            </tr>
            <tr>
                <td>Bob</td>
                <td>25</td>
                <td>LA</td>
            </tr>
        </tbody>
    </table>
    """
    soup = BeautifulSoup(html, "lxml")

    extractor = TableExtractor()
    field_config = FieldConfig(selector="table")

    result = await extractor.extract(soup, "data", field_config)

    assert len(result) == 2
    assert result[0]["Name"] == "Alice"
    assert result[0]["Age"] == "30"
    assert result[1]["Name"] == "Bob"
    assert result[1]["City"] == "LA"

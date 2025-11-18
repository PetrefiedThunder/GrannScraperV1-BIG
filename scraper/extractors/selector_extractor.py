"""
Selector-based extraction using CSS and XPath selectors.

Primary extraction mechanism for structured HTML.
"""

import logging
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag
from scraper.config.models import FieldConfig
from scraper.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class SelectorExtractor(BaseExtractor):
    """
    Extract data using CSS or XPath selectors.

    Supports:
    - CSS selectors (.class, #id, element[attr])
    - XPath selectors (//div[@class='foo'])
    - Attribute extraction (text, href, src, data-*, etc.)
    - Multiple values (returns list)
    """

    async def extract(
        self,
        soup: BeautifulSoup,
        field_name: str,
        field_config: FieldConfig,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Extract field using selector.

        Args:
            soup: Parsed HTML
            field_name: Field name
            field_config: Field configuration
            context: Optional context

        Returns:
            Extracted value(s)
        """
        if not field_config.selector:
            logger.warning(f"No selector for field {field_name}")
            return field_config.default

        try:
            # Determine if XPath or CSS
            is_xpath = field_config.selector.startswith(("//", "(/"))

            if is_xpath:
                elements = self._select_xpath(soup, field_config.selector)
            else:
                elements = soup.select(field_config.selector)

            if not elements:
                logger.debug(f"No elements found for selector: {field_config.selector}")
                return field_config.default

            # Extract values from elements
            if field_config.multiple:
                values = [
                    self._extract_from_element(elem, field_config)
                    for elem in elements
                ]
                # Filter out None values
                values = [v for v in values if v is not None]
                return values if values else field_config.default
            else:
                # Single value - use first element
                value = self._extract_from_element(elements[0], field_config)
                return value if value is not None else field_config.default

        except Exception as e:
            logger.error(f"Extraction error for {field_name}: {e}")
            return field_config.default

    def _select_xpath(self, soup: BeautifulSoup, xpath: str) -> list[Tag]:
        """
        Select elements using XPath (converted to CSS where possible).

        Args:
            soup: BeautifulSoup object
            xpath: XPath expression

        Returns:
            List of matching elements
        """
        # For simple XPath expressions, convert to CSS
        # Full XPath support would require lxml's xpath()
        # This is a simplified implementation for common cases

        # Convert common XPath patterns to CSS
        css_selector = xpath

        # //div -> div
        if xpath.startswith("//"):
            css_selector = xpath[2:]

        # //div[@class='foo'] -> div.foo
        if "[@class='" in css_selector or '[@class="' in css_selector:
            import re
            css_selector = re.sub(
                r"\[@class=['\"]([^'\"]+)['\"]\]",
                r".\1",
                css_selector
            )

        # //div[@id='foo'] -> div#foo
        if "[@id='" in css_selector or '[@id="' in css_selector:
            import re
            css_selector = re.sub(
                r"\[@id=['\"]([^'\"]+)['\"]\]",
                r"#\1",
                css_selector
            )

        # Try to select with converted selector
        try:
            return soup.select(css_selector)
        except Exception:
            logger.warning(f"Could not convert XPath {xpath} to CSS")
            return []

    def _extract_from_element(
        self, element: Tag, field_config: FieldConfig
    ) -> Optional[str]:
        """
        Extract value from a single element.

        Args:
            element: BeautifulSoup Tag
            field_config: Field configuration

        Returns:
            Extracted string value or None
        """
        if not isinstance(element, Tag):
            return None

        attr = field_config.attr or "text"
        value: Optional[str] = None

        if attr == "text":
            # Get text content
            value = element.get_text(strip=True)
        elif attr == "html":
            # Get inner HTML
            value = str(element)
        else:
            # Get HTML attribute
            value = element.get(attr)
            if value and isinstance(value, list):
                value = " ".join(value)

        # Clean up value
        if value:
            value = value.strip()

            # Apply regex if configured
            if field_config.regex:
                value = self._apply_regex(value, field_config.regex)

        return value if value else None


class TableExtractor(BaseExtractor):
    """
    Extract data from HTML tables.

    Converts tables to structured data automatically.
    """

    async def extract(
        self,
        soup: BeautifulSoup,
        field_name: str,
        field_config: FieldConfig,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Extract table data.

        Args:
            soup: Parsed HTML
            field_name: Field name
            field_config: Field configuration
            context: Optional context

        Returns:
            List of dicts representing table rows
        """
        if not field_config.selector:
            return field_config.default

        try:
            table = soup.select_one(field_config.selector)
            if not table:
                return field_config.default

            return self._parse_table(table)

        except Exception as e:
            logger.error(f"Table extraction error for {field_name}: {e}")
            return field_config.default

    def _parse_table(self, table: Tag) -> list[dict[str, str]]:
        """
        Parse HTML table to list of dicts.

        Args:
            table: Table element

        Returns:
            List of row dicts with column headers as keys
        """
        rows = []

        # Find headers
        headers = []
        header_row = table.find("thead")
        if header_row:
            headers = [
                th.get_text(strip=True)
                for th in header_row.find_all(["th", "td"])
            ]
        else:
            # Try first row
            first_row = table.find("tr")
            if first_row:
                headers = [
                    th.get_text(strip=True)
                    for th in first_row.find_all(["th", "td"])
                ]

        # Find data rows
        tbody = table.find("tbody") or table
        data_rows = tbody.find_all("tr")

        # Skip header row if we found headers in first row
        start_idx = 1 if not table.find("thead") and headers else 0

        for row in data_rows[start_idx:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            # Build row dict
            row_data = {}
            for i, cell in enumerate(cells):
                header = headers[i] if i < len(headers) else f"column_{i}"
                row_data[header] = cell.get_text(strip=True)

            rows.append(row_data)

        return rows


class MediaExtractor(BaseExtractor):
    """
    Extract media URLs (images, videos, PDFs).

    Handles responsive images, srcset, and lazy loading.
    """

    async def extract(
        self,
        soup: BeautifulSoup,
        field_name: str,
        field_config: FieldConfig,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Extract media URLs.

        Args:
            soup: Parsed HTML
            field_name: Field name
            field_config: Field configuration
            context: Optional context (with base_url)

        Returns:
            URL or list of URLs
        """
        if not field_config.selector:
            return field_config.default

        try:
            elements = soup.select(field_config.selector)
            if not elements:
                return field_config.default

            base_url = context.get("url") if context else None

            if field_config.multiple:
                urls = [
                    self._extract_media_url(elem, base_url)
                    for elem in elements
                ]
                urls = [url for url in urls if url]
                return urls if urls else field_config.default
            else:
                url = self._extract_media_url(elements[0], base_url)
                return url if url else field_config.default

        except Exception as e:
            logger.error(f"Media extraction error for {field_name}: {e}")
            return field_config.default

    def _extract_media_url(
        self, element: Tag, base_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract media URL from element.

        Args:
            element: HTML element
            base_url: Base URL for resolving relative URLs

        Returns:
            Absolute URL or None
        """
        url = None

        # Try different attributes
        if element.name == "img":
            # Try srcset first (responsive images)
            srcset = element.get("srcset")
            if srcset:
                # Parse srcset (simplified - takes first URL)
                url = srcset.split(",")[0].split()[0]
            else:
                url = element.get("src") or element.get("data-src")
        elif element.name == "video":
            url = element.get("src")
            # Try source child elements
            if not url:
                source = element.find("source")
                if source:
                    url = source.get("src")
        elif element.name == "a":
            url = element.get("href")
        else:
            url = element.get("src") or element.get("href")

        # Resolve relative URLs
        if url and base_url:
            from urllib.parse import urljoin
            url = urljoin(base_url, url)

        return url

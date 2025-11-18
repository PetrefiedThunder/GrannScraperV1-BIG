"""
Core scraping engine.

Orchestrates fetchers, extractors, pagination, and data flow.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.config.models import (
    FieldType,
    PaginationMode,
    ScrapeJob,
    ScrapeResult,
)
from scraper.core.fetcher_browser import BrowserFetcher
from scraper.core.fetcher_static import StaticFetcher
from scraper.core.rate_limiter import RateLimiter, SessionManager
from scraper.extractors.selector_extractor import (
    MediaExtractor,
    SelectorExtractor,
    TableExtractor,
)
from scraper.extractors.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)


class ScraperEngine:
    """
    Main scraping engine.

    Coordinates:
    - Fetching (static or browser)
    - Extraction (selectors, tables, media, LLM)
    - Pagination (next button, URL pattern, infinite scroll)
    - Rate limiting & session management
    - Result aggregation
    """

    def __init__(self):
        """Initialize scraper engine."""
        self.session_manager = SessionManager()

    async def run_job(self, job: ScrapeJob) -> ScrapeResult:
        """
        Execute a complete scrape job.

        Args:
            job: ScrapeJob configuration

        Returns:
            ScrapeResult with scraped data and metadata
        """
        logger.info(f"Starting job: {job.name}")
        start_time = datetime.utcnow()

        result = ScrapeResult(
            job_id=job.id,
            status="success",
            start_time=start_time,
        )

        try:
            # Initialize components
            rate_limiter = RateLimiter(job.rate_limit)
            selector_extractor = SelectorExtractor()
            table_extractor = TableExtractor()
            media_extractor = MediaExtractor()
            llm_extractor = LLMExtractor() if self._has_llm_fields(job) else None

            # Choose fetcher based on job config
            use_browser = job.browser.enabled or self._needs_browser(job)

            if use_browser:
                logger.info("Using browser fetcher")
                fetcher = BrowserFetcher(job)
            else:
                logger.info("Using static fetcher")
                fetcher = StaticFetcher(job)

            async with fetcher:
                # Generate URLs to scrape
                urls = await self._generate_urls(job)

                logger.info(f"Will scrape {len(urls)} URLs")

                # Scrape each URL
                for i, url in enumerate(urls):
                    if job.max_items and len(result.data) >= job.max_items:
                        logger.info(f"Reached max items limit: {job.max_items}")
                        break

                    # Rate limiting
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    await rate_limiter.acquire(domain)

                    try:
                        # Fetch page
                        soup, html = await fetcher.fetch(url)

                        if not soup:
                            result.errors.append(f"Failed to fetch {url}")
                            self.session_manager.mark_failed(url)
                            continue

                        self.session_manager.mark_visited(url)
                        result.pages_visited += 1

                        # Extract items from page
                        items = await self._extract_items(
                            soup,
                            html,
                            job,
                            url,
                            selector_extractor,
                            table_extractor,
                            media_extractor,
                            llm_extractor,
                        )

                        result.data.extend(items)
                        result.items_scraped += len(items)

                        logger.info(
                            f"Page {i + 1}/{len(urls)}: "
                            f"Extracted {len(items)} items "
                            f"(total: {result.items_scraped})"
                        )

                    except Exception as e:
                        error_msg = f"Error scraping {url}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)
                        self.session_manager.mark_failed(url)

                    finally:
                        rate_limiter.release(domain)

            # Finalize result
            result.end_time = datetime.utcnow()
            result.duration_seconds = (
                result.end_time - result.start_time
            ).total_seconds()

            if result.errors:
                result.status = "partial" if result.data else "failed"

            result.metadata = {
                "session_stats": self.session_manager.get_stats(),
                "job_name": job.name,
                "job_id": job.id,
            }

            logger.info(
                f"Job completed: {result.items_scraped} items, "
                f"{result.pages_visited} pages, "
                f"{len(result.errors)} errors"
            )

            return result

        except Exception as e:
            logger.error(f"Job failed: {e}")
            result.end_time = datetime.utcnow()
            result.status = "failed"
            result.errors.append(str(e))
            return result

    async def _generate_urls(self, job: ScrapeJob) -> list[str]:
        """
        Generate list of URLs to scrape based on pagination config.

        Args:
            job: ScrapeJob configuration

        Returns:
            List of URLs
        """
        urls = [job.start_url]

        pagination = job.pagination

        if pagination.mode == PaginationMode.NONE:
            return urls

        elif pagination.mode == PaginationMode.URL_PATTERN:
            # Generate URLs from pattern
            if pagination.url_pattern:
                urls = []
                for page_num in range(
                    pagination.start_page,
                    pagination.start_page + pagination.max_pages
                ):
                    url = pagination.url_pattern.format(page=page_num)
                    urls.append(url)

        elif pagination.mode == PaginationMode.NEXT_BUTTON:
            # Will handle dynamically during scraping
            # For now, return start URL
            pass

        elif pagination.mode == PaginationMode.INFINITE_SCROLL:
            # Handled by browser fetcher
            # Return single URL
            pass

        return urls

    async def _extract_items(
        self,
        soup: BeautifulSoup,
        html: str,
        job: ScrapeJob,
        url: str,
        selector_extractor: SelectorExtractor,
        table_extractor: TableExtractor,
        media_extractor: MediaExtractor,
        llm_extractor: Optional[LLMExtractor],
    ) -> list[dict[str, Any]]:
        """
        Extract items from a page.

        Args:
            soup: Parsed HTML
            html: Raw HTML
            job: Job configuration
            url: Current URL
            selector_extractor: Selector extractor
            table_extractor: Table extractor
            media_extractor: Media extractor
            llm_extractor: Optional LLM extractor

        Returns:
            List of extracted items (dicts)
        """
        items = []

        # If item_selector is provided, extract multiple items
        if job.item_selector:
            item_elements = soup.select(job.item_selector)
            logger.debug(f"Found {len(item_elements)} items with selector {job.item_selector}")

            for item_element in item_elements:
                # Create a soup for just this item
                item_soup = BeautifulSoup(str(item_element), "lxml")

                # Extract fields from this item
                item_data = await self._extract_fields(
                    item_soup,
                    job,
                    url,
                    selector_extractor,
                    table_extractor,
                    media_extractor,
                    llm_extractor,
                )

                if item_data:
                    items.append(item_data)

        else:
            # Extract from entire page (single item)
            item_data = await self._extract_fields(
                soup,
                job,
                url,
                selector_extractor,
                table_extractor,
                media_extractor,
                llm_extractor,
            )

            if item_data:
                items.append(item_data)

        return items

    async def _extract_fields(
        self,
        soup: BeautifulSoup,
        job: ScrapeJob,
        url: str,
        selector_extractor: SelectorExtractor,
        table_extractor: TableExtractor,
        media_extractor: MediaExtractor,
        llm_extractor: Optional[LLMExtractor],
    ) -> dict[str, Any]:
        """
        Extract all configured fields from soup.

        Args:
            soup: Parsed HTML (for single item or full page)
            job: Job configuration
            url: Current URL
            selector_extractor: Selector extractor
            table_extractor: Table extractor
            media_extractor: Media extractor
            llm_extractor: Optional LLM extractor

        Returns:
            Dict of field values
        """
        data = {}
        context = {"url": url}

        for field_name, field_config in job.fields.items():
            try:
                # Choose extractor based on config
                if field_config.use_llm and llm_extractor:
                    value = await llm_extractor.extract(
                        soup, field_name, field_config, context
                    )
                elif field_config.selector and "table" in field_config.selector.lower():
                    # Heuristic: if selector contains "table", use table extractor
                    value = await table_extractor.extract(
                        soup, field_name, field_config, context
                    )
                elif field_config.type in (FieldType.URL,) or "img" in str(field_config.selector):
                    # Use media extractor for images/videos
                    value = await media_extractor.extract(
                        soup, field_name, field_config, context
                    )
                else:
                    # Default: selector extractor
                    value = await selector_extractor.extract(
                        soup, field_name, field_config, context
                    )

                # Type conversion
                if value is not None:
                    value = self._convert_type(value, field_config.type)

                data[field_name] = value

            except Exception as e:
                logger.error(f"Error extracting field {field_name}: {e}")
                data[field_name] = field_config.default

        return data

    def _convert_type(self, value: Any, field_type: FieldType) -> Any:
        """
        Convert extracted value to proper type.

        Args:
            value: Raw extracted value
            field_type: Target field type

        Returns:
            Typed value
        """
        if value is None or value == "":
            return None

        try:
            if field_type == FieldType.INT:
                # Handle strings with commas
                if isinstance(value, str):
                    value = value.replace(",", "")
                return int(float(value))

            elif field_type == FieldType.FLOAT:
                if isinstance(value, str):
                    value = value.replace(",", "")
                return float(value)

            elif field_type == FieldType.BOOL:
                if isinstance(value, str):
                    return value.lower() in ("true", "yes", "1", "on")
                return bool(value)

            elif field_type == FieldType.CURRENCY:
                # Extract numeric value from currency string
                if isinstance(value, str):
                    import re
                    match = re.search(r"[\d,]+\.?\d*", value)
                    if match:
                        return float(match.group().replace(",", ""))
                return float(value)

            elif field_type == FieldType.DATE:
                # Parse date
                from dateutil import parser
                return parser.parse(value)

            elif field_type == FieldType.DATETIME:
                from dateutil import parser
                return parser.parse(value)

            else:
                return str(value)

        except Exception as e:
            logger.warning(f"Type conversion failed for {value} -> {field_type}: {e}")
            return value

    def _has_llm_fields(self, job: ScrapeJob) -> bool:
        """Check if job has any LLM-enabled fields."""
        return any(field.use_llm for field in job.fields.values())

    def _needs_browser(self, job: ScrapeJob) -> bool:
        """Determine if job needs browser based on config."""
        # Use browser if:
        # - Explicitly enabled
        # - Infinite scroll pagination
        # - Has wait_for_selector
        return (
            job.browser.enabled
            or job.pagination.mode == PaginationMode.INFINITE_SCROLL
            or bool(job.browser.wait_for_selector)
        )

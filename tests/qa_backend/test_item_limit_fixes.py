"""BE-006: accepted rows never exceed a configured positive item budget."""

from typing import Self

import pytest
from bs4 import BeautifulSoup

from scraper.config.models import PaginationConfig, ScrapeJob
from scraper.core import engine as engine_module
from scraper.core.engine import ScraperEngine


@pytest.fixture
def fetched_pages(job: ScrapeJob, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    fetched: list[str] = []

    class FixtureFetcher:
        def __init__(self, config: ScrapeJob) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def fetch(self, url: str) -> tuple[BeautifulSoup, str]:
            fetched.append(url)
            page = int(url.rsplit("/", 1)[1])
            html = "".join(
                f"<article><h2>Item {item}</h2></article>"
                for item in range((page - 1) * 3 + 1, page * 3 + 1)
            )
            html += f'<a class="next" href="/page/{page + 1}">Next</a>'
            return BeautifulSoup(html, "lxml"), html

    monkeypatch.setattr(engine_module, "StaticFetcher", FixtureFetcher)
    monkeypatch.setattr(engine_module, "BrowserFetcher", FixtureFetcher)
    job.pagination = PaginationConfig(
        mode="next_button", next_button_selector=".next", max_pages=3,
    )
    return fetched


@pytest.mark.parametrize("browser", [False, True])
@pytest.mark.parametrize("limit", [1, 3, 4, 6, 20])
async def test_accepted_rows_respect_remaining_item_budget(
    job: ScrapeJob, fetched_pages: list[str], browser: bool, limit: int,
) -> None:
    job.browser.enabled = browser
    job.max_items = limit
    result = await ScraperEngine().run_job(job)
    count = min(limit, 9)
    page_count = (count + 2) // 3
    assert result.status == "success"
    assert result.items_scraped == count
    assert result.data == [{"title": f"Item {item}"} for item in range(1, count + 1)]
    assert result.pages_visited == page_count
    assert fetched_pages == [
        f"https://fixture.invalid/page/{page}" for page in range(1, page_count + 1)
    ]


@pytest.mark.parametrize("limit", [None, 0])
async def test_existing_unlimited_item_settings_are_preserved(
    job: ScrapeJob, fetched_pages: list[str], limit: int | None,
) -> None:
    job.max_items = limit
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert result.items_scraped == 9
    assert len(result.data) == 9
    assert len(fetched_pages) == 3

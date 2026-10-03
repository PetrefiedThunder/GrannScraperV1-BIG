"""BE-009: bounded next-link pagination through offline HTML fixtures."""

import asyncio
from html import escape
from typing import Self
from unittest.mock import AsyncMock

import httpx
import pytest
from bs4 import BeautifulSoup

from scraper.api import rest_server as api
from scraper.config.models import PaginationConfig, ScrapeJob
from scraper.core import engine as engine_module
from scraper.core.engine import ScraperEngine

PageFixture = tuple[dict[str, tuple[str, str | None]], list[str]]


@pytest.fixture
def page_fetcher(job: ScrapeJob, monkeypatch: pytest.MonkeyPatch) -> PageFixture:
    pages: dict[str, tuple[str, str | None]] = {}
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
            title, next_link = pages[url]
            html = f"<article><h2>{escape(title)}</h2></article>"
            if next_link is not None:
                html += f'<a class="next" href="{escape(next_link, quote=True)}">Next</a>'
            return BeautifulSoup(html, "lxml"), html

    monkeypatch.setattr(engine_module, "StaticFetcher", FixtureFetcher)
    monkeypatch.setattr(engine_module, "BrowserFetcher", FixtureFetcher)
    job.pagination = PaginationConfig(
        mode="next_button", next_button_selector=".next", max_pages=10,
    )
    return pages, fetched


@pytest.mark.parametrize("browser", [False, True])
async def test_next_links_resolve_against_each_current_page(
    job: ScrapeJob, page_fetcher: PageFixture, browser: bool,
) -> None:
    pages, fetched = page_fetcher
    job.browser.enabled = browser
    pages.update({
        job.start_url: ("One", "/page/2/"),
        "https://fixture.invalid/page/2/": ("Two", "../3#results"),
        "https://fixture.invalid/page/3": ("Three", None),
    })
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert fetched == list(pages)
    assert result.pages_visited == 3
    assert [item["title"] for item in result.data] == ["One", "Two", "Three"]


@pytest.mark.parametrize("max_pages", [1, 2])
async def test_next_links_stop_at_page_limit(
    job: ScrapeJob, page_fetcher: PageFixture, max_pages: int,
) -> None:
    pages, fetched = page_fetcher
    job.pagination.max_pages = max_pages
    pages.update({
        job.start_url: ("One", "/page/2"),
        "https://fixture.invalid/page/2": ("Two", "/page/3"),
    })
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert fetched == list(pages)[:max_pages]
    assert result.pages_visited == max_pages


@pytest.mark.parametrize("back_link", ["/page/1", "/page/1#results"])
async def test_next_links_stop_on_cycles(
    job: ScrapeJob, page_fetcher: PageFixture, back_link: str,
) -> None:
    pages, fetched = page_fetcher
    pages.update({
        job.start_url: ("One", "/page/2"),
        "https://fixture.invalid/page/2": ("Two", back_link),
    })
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert fetched == list(pages)
    assert result.pages_visited == 2


@pytest.mark.parametrize("next_link", [
    None, "", "#results", "javascript:void(0)", "data:text/html,page",
    "file:///page/2", "https://other.invalid/page/2",
    "https://fixture.invalid.other.invalid/page/2",
    "https://notfixture.invalid/page/2", "https://[invalid/page/2",
    "https://fixture.invalid:bad/page/2", "https://user:password@fixture.invalid/page/2",
])
async def test_next_links_reject_missing_unsafe_or_outside_links(
    job: ScrapeJob, page_fetcher: PageFixture, next_link: str | None,
) -> None:
    pages, fetched = page_fetcher
    pages[job.start_url] = ("One", next_link)
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert fetched == [job.start_url]
    assert result.pages_visited == 1


async def test_next_links_allow_configured_subdomains(
    job: ScrapeJob, page_fetcher: PageFixture,
) -> None:
    pages, fetched = page_fetcher
    pages.update({
        job.start_url: ("One", "https://sub.fixture.invalid/page/2"),
        "https://sub.fixture.invalid/page/2": ("Two", None),
    })
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert fetched == list(pages)
    assert result.pages_visited == 2


@pytest.mark.parametrize("mode", ["", "?concurrent=true", "?incremental=true"])
@pytest.mark.parametrize("max_pages", [1, 2])
async def test_api_next_links_persist_complete_bounded_results(
    client: httpx.AsyncClient,
    job: ScrapeJob,
    page_fetcher: PageFixture,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    max_pages: int,
) -> None:
    pages, fetched = page_fetcher
    job.pagination.max_pages = max_pages
    pages.update({
        job.start_url: ("One", "/page/2"),
        "https://fixture.invalid/page/2": ("Two", "/page/3"),
    })
    api.jobs_db[job.id] = job
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    assert (await client.post(f"/api/v1/jobs/{job.id}/run{mode}")).status_code == 200
    result = await asyncio.wait_for(api.running_jobs[job.id], 1)
    assert result.status == "success"
    assert result.pages_visited == max_pages
    assert fetched == list(pages)[:max_pages]
    response = (await client.get(f"/api/v1/jobs/{job.id}/results")).json()
    assert response["items"] == [{"title": title} for title in ["One", "Two"][:max_pages]]
    assert response["pages_visited"] == max_pages
    assert response["total_items"] == max_pages

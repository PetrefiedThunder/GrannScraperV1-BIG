"""Deterministic engine and API lifecycle checks with no real fetches."""

import asyncio
from unittest.mock import AsyncMock

from bs4 import BeautifulSoup
import pytest

from scraper.api import rest_server as api
from scraper.config.models import ScrapeResult
from scraper.core import engine as engine_module
from scraper.core.concurrent_engine import ConcurrentScraper
from scraper.core.engine import ScraperEngine
from scraper.scheduler.workflow_dag import WorkflowDAG, WorkflowNode
from scraper.storage.smart_cache import IncrementalScraper, SmartCache


async def test_standard_api_run_persists_success(client, job, monkeypatch):
    api.jobs_db[job.id] = job
    expected = ScrapeResult(job_id=job.id, status="success", items_scraped=1, data=[{"title": "one"}])
    monkeypatch.setattr(ScraperEngine, "run_job", AsyncMock(return_value=expected))
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    response = await client.post(f"/api/v1/jobs/{job.id}/run")
    assert response.status_code == 200
    task = api.running_jobs[job.id]
    outcome = await asyncio.gather(task, return_exceptions=True)
    assert outcome == [expected], f"Background execution returned: {outcome!r}"
    status = (await client.get(f"/api/v1/jobs/{job.id}/status")).json()
    assert status["status"] == "success"
    assert status["is_running"] is False


async def test_concurrent_scraper_finishes_after_completed_work(job, monkeypatch):
    scraper = ConcurrentScraper(job, max_workers=2)
    await scraper.add_urls([job.start_url])
    completed = asyncio.Event()

    async def fetch(url):
        completed.set()
        return [{"url": url}]

    # Preserve the real worker logic, reducing only its idle timeout for this
    # bounded offline test. No production network or arbitrary multi-second wait.
    original_wait_for = asyncio.wait_for

    async def fast_idle_timeout(awaitable, timeout):
        return await original_wait_for(awaitable, 0.001 if timeout in (5.0, 10.0) else timeout)

    monkeypatch.setattr(asyncio, "wait_for", fast_idle_timeout)
    task = asyncio.create_task(scraper.run(fetch))
    await original_wait_for(completed.wait(), 1)
    done, _ = await asyncio.wait([task], timeout=0.1)
    finished = task in done
    if not finished:
        task.cancel()
    outcome = await asyncio.gather(task, return_exceptions=True)
    assert scraper.completed_tasks == 1
    assert finished, "Result collected but idle workers never finish; active_workers is zero"
    assert outcome[0].items_scraped == 1


async def test_incremental_api_run_accepts_engine_result(client, job, monkeypatch):
    api.jobs_db[job.id] = job
    expected = ScrapeResult(job_id=job.id, status="success", items_scraped=1, data=[{"title": "one"}])
    monkeypatch.setattr(ScraperEngine, "run_job", AsyncMock(return_value=expected))
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    response = await client.post(f"/api/v1/jobs/{job.id}/run?incremental=true")
    assert response.status_code == 200
    outcome = await asyncio.gather(api.running_jobs[job.id], return_exceptions=True)
    assert isinstance(outcome[0], ScrapeResult), f"Incremental callback returned {outcome!r}"
    assert outcome[0].data == expected.data


async def test_incremental_repeat_uses_cache(job, tmp_path):
    scraper = IncrementalScraper(SmartCache(tmp_path / "repeat-cache"))
    fetch = AsyncMock(return_value=[{"title": "one"}])
    first = await scraper.scrape_incremental([job.start_url], fetch)
    second = await scraper.scrape_incremental([job.start_url], fetch)
    assert first["stats"]["urls_scraped"] == 1
    assert second["stats"]["urls_scraped"] == 0
    assert fetch.await_count == 1


async def test_incremental_cached_items_are_returned(job, tmp_path):
    cache = SmartCache(tmp_path / "prepopulated-cache")
    cache.cache_page(job.start_url, "<p>one</p>")
    cache.cache_items([{"title": "one"}], job.start_url)
    fetch = AsyncMock()
    result = await IncrementalScraper(cache).scrape_incremental([job.start_url], fetch)
    fetch.assert_not_awaited()
    assert result["cached_items"] == [{"title": "one"}]


def test_workflow_orders_prerequisites_before_dependents():
    workflow = WorkflowDAG("qa-chain")
    workflow.add_node(WorkflowNode(id="fetch", type="scrape"))
    workflow.add_node(WorkflowNode(id="export", type="export", depends_on=["fetch"]))
    workflow.build()
    assert workflow.execution_order == [["fetch"], ["export"]]


class FixtureFetcher:
    """Local HTML transport substitute, with exact URL requests recorded."""

    def __init__(self, job):
        self.urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def fetch(self, url):
        self.urls.append(url)
        html = "<article><h2>One</h2></article><article><h2>Two</h2></article><article><h2>Three</h2></article>"
        return BeautifulSoup(html, "lxml"), html


async def test_engine_extracts_and_counts_fixture_items(job, monkeypatch):
    monkeypatch.setattr(engine_module, "StaticFetcher", FixtureFetcher)
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert result.items_scraped == 3
    assert result.pages_visited == 1
    assert [item["title"] for item in result.data] == ["One", "Two", "Three"]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BE-006: max_items is checked only before a page and allows page overshoot")
async def test_engine_respects_item_limit_within_page(job, monkeypatch):
    monkeypatch.setattr(engine_module, "StaticFetcher", FixtureFetcher)
    job.max_items = 1
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert result.items_scraped == 1
    assert len(result.data) == 1


async def test_engine_converts_transport_failure_to_terminal_result(job, monkeypatch):
    class FailedFetcher(FixtureFetcher):
        async def fetch(self, url):
            raise OSError("offline fixture transport unavailable")

    monkeypatch.setattr(engine_module, "StaticFetcher", FailedFetcher)
    result = await ScraperEngine().run_job(job)
    assert result.status == "failed"
    assert result.items_scraped == 0
    assert len(result.errors) == 1
    assert result.end_time is not None


async def test_engine_follows_next_button(job, monkeypatch):
    fetched = []

    class PaginatedFetcher(FixtureFetcher):
        async def fetch(self, url):
            fetched.append(url)
            html = "<article><h2>One</h2></article>"
            if url.endswith("/1"):
                html += '<a class="next" href="/page/2">Next</a>'
            return BeautifulSoup(html, "lxml"), html

    monkeypatch.setattr(engine_module, "StaticFetcher", PaginatedFetcher)
    job.pagination.mode = "next_button"
    job.pagination.next_button_selector = ".next"
    job.pagination.max_pages = 2
    result = await ScraperEngine().run_job(job)
    assert result.status == "success"
    assert fetched == ["https://fixture.invalid/page/1", "https://fixture.invalid/page/2"]
    assert result.pages_visited == 2

"""BE-003: incremental API callbacks operate on individual URLs and replay data."""

from unittest.mock import AsyncMock

import httpx
import pytest

from scraper.api import rest_server as api
from scraper.config.models import PaginationMode, ScrapeJob, ScrapeResult


async def run_incremental(client: httpx.AsyncClient, job: ScrapeJob) -> ScrapeResult:
    response = await client.post(f"/api/v1/jobs/{job.id}/run?incremental=true")
    assert response.status_code == 200
    return await api.running_jobs[job.id]


async def test_incremental_api_fetches_each_url_once_and_replays_items(
    client: httpx.AsyncClient, job: ScrapeJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    job.pagination.mode = PaginationMode.URL_PATTERN
    job.pagination.url_pattern = "https://fixture.invalid/page/{page}"
    job.pagination.max_pages = 2
    api.jobs_db[job.id] = job
    seen = []

    async def scrape(_self: api.ScraperEngine, page_job: ScrapeJob) -> ScrapeResult:
        seen.append(page_job)
        return ScrapeResult(
            job_id=job.id,
            status="success",
            pages_visited=1,
            items_scraped=1,
            data=[{"url": page_job.start_url}],
        )

    monkeypatch.setattr(api.ScraperEngine, "run_job", scrape)
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    first = await run_incremental(client, job)
    replay = await run_incremental(client, job)
    assert first.status == replay.status == "success"
    assert (
        first.data
        == replay.data
        == [
            {"url": "https://fixture.invalid/page/1"},
            {"url": "https://fixture.invalid/page/2"},
        ]
    )
    assert first.items_scraped == replay.items_scraped == 2
    assert len(seen) == 2
    assert all(page.pagination.mode == "none" for page in seen)
    assert all(page.rate_limit == job.rate_limit and page.fields == job.fields for page in seen)
    assert job.pagination.mode == "url_pattern"
    assert first.pages_visited == 2
    assert replay.pages_visited == 0
    assert replay.metadata["urls_cached"] == 2


@pytest.mark.parametrize("status", ["failed", "partial"])
async def test_incremental_failed_page_is_not_cached_as_success(
    client: httpx.AsyncClient, job: ScrapeJob, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    api.jobs_db[job.id] = job
    failed = ScrapeResult(job_id=job.id, status=status, errors=["fixture failure"])
    succeeded = ScrapeResult(
        job_id=job.id, status="success", data=[{"title": "recovered"}], items_scraped=1
    )
    scrape = AsyncMock(side_effect=[failed, succeeded])
    monkeypatch.setattr(api.ScraperEngine, "run_job", scrape)
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    first = await run_incremental(client, job)
    assert first.status == "failed"
    assert first.errors == ["Job execution failed"]
    recovered = await run_incremental(client, job)
    assert recovered.status == "success"
    assert recovered.data == succeeded.data
    assert scrape.await_count == 2


async def test_incremental_api_cache_isolated_by_job_configuration(
    client: httpx.AsyncClient, job: ScrapeJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    api.jobs_db[job.id] = job
    first = ScrapeResult(job_id=job.id, status="success", data=[{"title": "one"}], items_scraped=1)
    changed = ScrapeResult(
        job_id=job.id, status="success", data=[{"price": "two"}], items_scraped=1
    )
    scrape = AsyncMock(side_effect=[first, changed])
    monkeypatch.setattr(api.ScraperEngine, "run_job", scrape)
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    assert (await run_incremental(client, job)).data == first.data
    other_job = job.model_copy(deep=True)
    other_job.id = "qa_other"
    other_job.fields = {"price": job.fields["title"].model_copy(update={"selector": "span"})}
    api.jobs_db[other_job.id] = other_job
    assert (await run_incremental(client, other_job)).data == changed.data
    assert (await run_incremental(client, job)).data == first.data
    assert scrape.await_count == 2

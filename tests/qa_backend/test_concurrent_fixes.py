"""BE-002: concurrent jobs release workers on every terminal path."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import cast
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from scraper.api import rest_server as api
from scraper.config.models import ScrapeJob, ScrapeResult
from scraper.core.concurrent_engine import ConcurrentScraper


async def test_concurrent_api_run_reaches_terminal_result(
    client: AsyncClient, job: ScrapeJob, monkeypatch: pytest.MonkeyPatch,
) -> None:
    api.jobs_db[job.id] = job
    expected = ScrapeResult(
        job_id=job.id, status="success", data=[{"title": "one"}], items_scraped=1,
    )
    monkeypatch.setattr(api.ScraperEngine, "run_job", AsyncMock(return_value=expected))
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    assert (await client.post(f"/api/v1/jobs/{job.id}/run?concurrent=true")).status_code == 200
    result = await asyncio.wait_for(api.running_jobs[job.id], 1)
    assert result.data == expected.data
    status = (await client.get(f"/api/v1/jobs/{job.id}/status")).json()
    assert status["status"] == "success"
    assert status["is_running"] is False


@pytest.fixture
async def worker_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[list[asyncio.Task[None]]]:
    """Observe worker lifetime and clean up the pre-fix negative control."""
    tasks: list[asyncio.Task[None]] = []
    original_worker = ConcurrentScraper.worker

    async def record_worker(
        self: ConcurrentScraper,
        worker_id: int,
        scrape_func: Callable[[str], Awaitable[object]],
    ) -> None:
        tasks.append(cast(asyncio.Task[None], asyncio.current_task()))
        return await original_worker(self, worker_id, scrape_func)

    monkeypatch.setattr(ConcurrentScraper, "worker", record_worker)
    yield tasks
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def test_concurrent_empty_queue_finishes(
    job: ScrapeJob, worker_tasks: list[asyncio.Task[None]],
) -> None:
    scraper = ConcurrentScraper(job, max_workers=2)
    fetch = AsyncMock()

    result = await asyncio.wait_for(scraper.run(fetch), timeout=0.5)

    assert result.status == "success"
    assert result.items_scraped == result.pages_visited == 0
    fetch.assert_not_awaited()
    assert all(task.done() for task in worker_tasks)


@pytest.mark.parametrize("outcome", [[], RuntimeError("fixture failed")])
async def test_concurrent_failed_work_finishes(
    job: ScrapeJob,
    worker_tasks: list[asyncio.Task[None]],
    outcome: list[dict[str, str]] | Exception,
) -> None:
    job.retry.max_retries = 0
    scraper = ConcurrentScraper(job, max_workers=2)
    await scraper.add_urls([job.start_url])
    if isinstance(outcome, Exception):
        fetch = AsyncMock(side_effect=outcome)
    else:
        fetch = AsyncMock(return_value=outcome)

    result = await asyncio.wait_for(scraper.run(fetch), timeout=0.5)

    assert result.status == "failed"
    assert len(result.errors) == 1
    assert result.metadata["failed_tasks"] == 1
    assert scraper.active_workers == 0
    assert all(task.done() for task in worker_tasks)


async def test_concurrent_retry_finishes_with_one_terminal_result(
    job: ScrapeJob, worker_tasks: list[asyncio.Task[None]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    job.retry.max_retries = 1
    scraper = ConcurrentScraper(job, max_workers=2)
    await scraper.add_urls([job.start_url])
    fetch = AsyncMock(side_effect=[[], [{"title": "retried"}]])
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    result = await asyncio.wait_for(scraper.run(fetch), timeout=0.5)

    assert result.status == "success"
    assert result.data == [{"title": "retried"}]
    assert fetch.await_count == 2
    assert result.metadata["total_tasks"] == 1
    assert result.metadata["completed_tasks"] == 1
    assert scraper.get_progress()["pending"] == 0
    assert all(task.done() for task in worker_tasks)


async def test_concurrent_cancellation_stops_active_and_idle_workers(
    job: ScrapeJob, worker_tasks: list[asyncio.Task[None]],
) -> None:
    scraper = ConcurrentScraper(job, max_workers=2)
    await scraper.add_urls([job.start_url])
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def fetch(_url: str) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    run_task = asyncio.create_task(scraper.run(fetch))
    await asyncio.wait_for(started.wait(), timeout=0.5)
    run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(run_task, timeout=0.5)

    assert stopped.is_set()
    assert scraper.active_workers == 0
    assert len(worker_tasks) == 2
    assert all(task.done() for task in worker_tasks)


async def test_concurrent_callback_cancellation_propagates_and_stops_workers(
    job: ScrapeJob, worker_tasks: list[asyncio.Task[None]],
) -> None:
    scraper = ConcurrentScraper(job, max_workers=2)
    await scraper.add_urls([job.start_url])
    fetch = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(scraper.run(fetch), timeout=0.5)

    fetch.assert_awaited_once()
    assert scraper.active_workers == 0
    assert all(task.done() for task in worker_tasks)

"""BE-001: background jobs always expose a terminal outcome."""

import asyncio
from unittest.mock import AsyncMock

from fastapi import BackgroundTasks
import pytest

from scraper.api import rest_server as api
from scraper.config.models import ScrapeResult


@pytest.mark.parametrize("phase", ["scrape", "export"])
async def test_background_exception_persists_failed_result(client, job, monkeypatch, phase):
    api.jobs_db[job.id] = job
    expected = ScrapeResult(job_id=job.id, status="success", data=[{"title": "one"}], items_scraped=1)
    scrape = AsyncMock(return_value=expected)
    export = AsyncMock(return_value={})
    failing = scrape if phase == "scrape" else export
    failing.side_effect = RuntimeError("private fixture diagnostic")
    monkeypatch.setattr(api.ScraperEngine, "run_job", scrape)
    monkeypatch.setattr(api.ExportManager, "export_result", export)
    assert (await client.post(f"/api/v1/jobs/{job.id}/run")).status_code == 200
    result = await api.running_jobs[job.id]
    assert result.status == "failed"
    assert result.end_time is not None
    assert result.duration_seconds >= 0
    status = (await client.get(f"/api/v1/jobs/{job.id}/status")).json()
    assert status["has_result"] is True
    assert status["is_running"] is False
    assert status["status"] == "failed"
    response = await client.get(f"/api/v1/jobs/{job.id}/results")
    assert response.json()["errors"] == ["Job execution failed"]
    assert "private fixture diagnostic" not in response.text
    if phase == "export":
        assert response.json()["items"] == expected.data
    else:
        export.assert_not_awaited()


@pytest.mark.parametrize("delete", [False, True])
async def test_cancellation_cleans_up_and_does_not_resurrect_deleted_job(client, job, monkeypatch, delete):
    api.jobs_db[job.id] = job
    entered = asyncio.Event()

    async def blocked(_self, _job):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(api.ScraperEngine, "run_job", blocked)
    assert (await client.post(f"/api/v1/jobs/{job.id}/run")).status_code == 200
    task = api.running_jobs[job.id]
    await asyncio.wait_for(entered.wait(), 1)
    if delete:
        assert (await client.delete(f"/api/v1/jobs/{job.id}")).status_code == 200
    else:
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert job.id not in api.running_jobs
    if delete:
        assert job.id not in api.results_db
        assert job.id not in api.jobs_db
    else:
        assert api.results_db[job.id].status == "failed"
        assert api.results_db[job.id].errors == ["Job cancelled"]


async def test_rerun_clears_previous_result_and_can_finish(client, job, monkeypatch):
    api.jobs_db[job.id] = job
    api.results_db[job.id] = ScrapeResult(job_id=job.id, status="failed")
    gate = asyncio.Event()
    expected = ScrapeResult(job_id=job.id, status="success")

    async def blocked(_self, _job):
        await gate.wait()
        return expected

    monkeypatch.setattr(api.ScraperEngine, "run_job", blocked)
    monkeypatch.setattr(api.ExportManager, "export_result", AsyncMock(return_value={}))
    assert (await client.post(f"/api/v1/jobs/{job.id}/run")).status_code == 200
    task = api.running_jobs[job.id]
    status = (await client.get(f"/api/v1/jobs/{job.id}/status")).json()
    assert status["is_running"] is True
    assert status["has_result"] is False
    gate.set()
    assert await task == expected
    assert api.results_db[job.id] == expected


async def test_deleted_run_cannot_publish_into_recreated_job(job, monkeypatch):
    api.jobs_db[job.id] = job
    entered = asyncio.Event()

    async def blocked(_self, _job):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(api.ScraperEngine, "run_job", blocked)
    await api.run_job(job.id, BackgroundTasks(), False, False)
    old_task = api.running_jobs[job.id]
    await asyncio.wait_for(entered.wait(), 1)
    await api.delete_job(job.id)
    api.jobs_db[job.id] = job.model_copy(deep=True)
    await api.run_job(job.id, BackgroundTasks(), False, False)
    new_task = api.running_jobs[job.id]
    await asyncio.gather(old_task, return_exceptions=True)
    status = await api.get_job_status(job.id)
    assert old_task.cancelled()
    assert status["is_running"] is True
    assert status["has_result"] is False
    assert api.running_jobs[job.id] is new_task

"""Offline API fixtures; all state and file outputs are isolated per test."""

import asyncio
from pathlib import Path

import httpx
import pytest

from scraper.api import rest_server as api
from scraper.config.models import ScrapeJob


@pytest.fixture(autouse=True)
async def isolated_api(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "jobs_db", {})
    monkeypatch.setattr(api, "results_db", {})
    monkeypatch.setattr(api, "workflows_db", {})
    monkeypatch.setattr(api, "running_jobs", {})
    monkeypatch.setattr(api, "jobs_lock", asyncio.Lock())
    # Cache APIs must never access the operator's default home cache.
    real_cache = api.SmartCache
    monkeypatch.setattr(api, "SmartCache", lambda: real_cache(tmp_path / "cache"))
    yield
    pending = list(api.running_jobs.values())
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://qa.invalid") as value:
        yield value


@pytest.fixture
def job(tmp_path: Path):
    return ScrapeJob(
        id="qa_job",
        name="QA fixture",
        start_url="https://fixture.invalid/page/1",
        item_selector="article",
        fields={"title": {"selector": "h2"}},
        rate_limit={"enabled": False},
        export={"base_path": tmp_path / "exports", "formats": ["json"]},
    )

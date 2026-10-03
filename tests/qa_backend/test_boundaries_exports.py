"""Bounded property tests, real HTTPX mock transport, and local export round trips."""

import csv
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
from hypothesis import given, settings, strategies as st
import pytest

from scraper.config.models import ScrapeJob, ScrapeResult
from scraper.core import fetcher_static
from scraper.core.engine import ScraperEngine
from scraper.export.export_manager import ExportManager


@settings(max_examples=50, derandomize=True, database=None, deadline=None)
@given(start=st.integers(min_value=1, max_value=100), count=st.integers(min_value=1, max_value=30))
async def test_url_pattern_generates_exact_contiguous_window(start, count):
    job = ScrapeJob(
        name="property fixture", start_url="https://fixture.invalid/items/1",
        pagination={"mode": "url_pattern", "url_pattern": "https://fixture.invalid/items/{page}",
                    "start_page": start, "max_pages": count},
    )
    urls = await ScraperEngine()._generate_urls(job)
    assert len(urls) == count
    assert len(set(urls)) == count
    assert urls == [f"https://fixture.invalid/items/{index}" for index in range(start, start + count)]


@pytest.mark.parametrize(("statuses", "expected_calls", "success"), [
    ([200], 1, True), ([503, 200], 2, True), ([400], 1, False), ([503, 503], 2, False),
])
async def test_static_fetcher_retry_classes(job, monkeypatch, statuses, expected_calls, success):
    monkeypatch.setattr(fetcher_static, "UserAgent", lambda: SimpleNamespace(random="qa-fixture", chrome="qa-fixture"))
    monkeypatch.setattr(fetcher_static.asyncio, "sleep", AsyncMock())
    job.retry.max_retries = 1
    calls = []

    def response(request):
        calls.append(request.url)
        return httpx.Response(statuses[min(len(calls) - 1, len(statuses) - 1)], text="<h1>Fixture</h1>")

    fetcher = fetcher_static.StaticFetcher(job)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as session:
        fetcher.session = session
        soup, html = await fetcher.fetch(job.start_url)
    assert len(calls) == expected_calls
    assert (soup is not None) is success
    assert (html is not None) is success


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BE-007: proxy-enabled fetch passes unsupported proxies keyword to AsyncClient.get")
async def test_proxy_enabled_fetch_reaches_configured_transport(job, monkeypatch):
    monkeypatch.setattr(fetcher_static, "UserAgent", lambda: SimpleNamespace(random="qa-fixture", chrome="qa-fixture"))
    job.proxy.enabled = True
    job.proxy.proxy_list = ["http://proxy.fixture.invalid:8080"]
    calls = []

    def response(request):
        calls.append(request.url)
        return httpx.Response(200, text="<h1>Fixture</h1>")

    fetcher = fetcher_static.StaticFetcher(job)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as session:
        fetcher.session = session
        soup, _ = await fetcher.fetch(job.start_url)
    assert soup is not None, "TypeError from unsupported request-level proxy argument is swallowed"
    assert len(calls) == 1


@pytest.mark.parametrize("format_name", ["json", "ndjson", "csv", "sqlite"])
async def test_local_export_round_trip(job, format_name):
    data = [{"title": "Café, one", "quantity": 2}, {"title": 'Line\n"two"', "quantity": 0}]
    job.export.formats = [format_name]
    result = ScrapeResult(
        job_id=job.id, status="success", data=data, items_scraped=2,
        metadata={"job_name": "qa_fixture"},
    )
    exported = await ExportManager(job.export).export_result(result)
    path = exported[format_name]
    assert path.is_relative_to(job.export.base_path)
    if format_name == "json":
        content = json.loads(path.read_text())
        assert content["items"] == data
        assert content["count"] == 2
    elif format_name == "ndjson":
        assert [json.loads(line) for line in path.read_text().splitlines()] == data
    elif format_name == "csv":
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows == [{"title": item["title"], "quantity": str(item["quantity"])} for item in data]
    else:
        with sqlite3.connect(path) as connection:
            rows = connection.execute("SELECT title, quantity FROM scraped_data ORDER BY rowid").fetchall()
        assert rows == [(item["title"], str(item["quantity"])) for item in data]

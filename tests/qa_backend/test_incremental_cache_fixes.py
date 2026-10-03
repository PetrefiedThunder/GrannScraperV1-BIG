"""BE-003: incremental cache replay and failed refresh regressions."""

from datetime import datetime, timedelta
import json
import sqlite3
from unittest.mock import AsyncMock

import pytest

from scraper.storage.smart_cache import IncrementalScraper, SmartCache


@pytest.fixture
def cache(tmp_path):
    return SmartCache(tmp_path / "incremental-cache")


def expire(cache, url):
    with sqlite3.connect(cache.db_path) as conn:
        conn.execute(
            "UPDATE page_cache SET scraped_at = ? WHERE url = ?",
            ((datetime.utcnow() - timedelta(hours=2)).isoformat(), url),
        )


async def test_be003_empty_success_is_fresh(cache):
    fetch = AsyncMock(return_value=[])
    scraper = IncrementalScraper(cache)
    await scraper.scrape_incremental(["https://fixture.invalid/empty"], fetch)
    replay = await scraper.scrape_incremental(["https://fixture.invalid/empty"], fetch)
    assert replay["cached_items"] == []
    assert replay["stats"]["urls_cached"] == 1
    fetch.assert_awaited_once()


@pytest.mark.parametrize("updated", [[{"title": "new"}], []])
async def test_be003_refresh_replaces_previous_items(cache, updated):
    url = "https://fixture.invalid/changing"
    fetch = AsyncMock(side_effect=[[{"title": "old"}], updated])
    scraper = IncrementalScraper(cache)
    await scraper.scrape_incremental([url], fetch)
    expire(cache, url)
    await scraper.scrape_incremental([url], fetch)
    replay = await scraper.scrape_incremental([url], fetch)
    assert replay["cached_items"] == updated
    assert fetch.await_count == 2


async def test_be003_replay_preserves_url_item_order_and_shared_items(cache):
    urls = ["https://fixture.invalid/b", "https://fixture.invalid/a"]
    first = [{"title": "shared"}, {"title": "b-only"}]
    second = [{"title": "a-only"}, {"title": "shared"}]
    fetch = AsyncMock(side_effect=[first, second])
    scraper = IncrementalScraper(cache)
    await scraper.scrape_incremental(urls, fetch)
    replay = await scraper.scrape_incremental(urls, fetch)
    assert replay["cached_items"] == first + second
    assert fetch.await_count == 2
    assert (await scraper.scrape_incremental([urls[0]], fetch))["cached_items"] == first


async def test_be003_refresh_preserves_existing_html_and_page_metadata(cache):
    url = "https://fixture.invalid/existing"
    cache.cache_page(url, "<p>original</p>", etag="fixture-etag", last_modified="fixture-date", metadata={"fixture": True})
    expire(cache, url)
    await IncrementalScraper(cache).scrape_incremental([url], AsyncMock(return_value=[{"title": "one"}]))
    assert cache.get_cached_content(url) == "<p>original</p>"
    with sqlite3.connect(cache.db_path) as conn:
        row = conn.execute("SELECT content_hash, etag, last_modified, metadata FROM page_cache WHERE url = ?", (url,)).fetchone()
    assert row[:3] == (cache._hash_content("<p>original</p>"), "fixture-etag", "fixture-date")
    assert json.loads(row[3])["fixture"] is True


async def test_be003_failure_does_not_make_url_fresh(cache):
    url = "https://fixture.invalid/failed"
    scraper = IncrementalScraper(cache)
    failed_fetch = AsyncMock(side_effect=RuntimeError("fixture failure"))
    with pytest.raises(RuntimeError, match="fixture failure"):
        await scraper.scrape_incremental([url], failed_fetch)
    assert cache.should_scrape(url, 3600)[0] is True
    recovered = await scraper.scrape_incremental([url], AsyncMock(return_value=[{"title": "recovered"}]))
    assert recovered["new_items"] == [{"title": "recovered"}]
    expire(cache, url)
    with pytest.raises(RuntimeError, match="fixture failure"):
        await scraper.scrape_incremental([url], failed_fetch)
    assert cache.should_scrape(url, 3600)[0] is True


@pytest.mark.parametrize("invalid_items", [None, {"title": "one"}, ["invalid item"]])
async def test_be003_invalid_callback_result_is_not_cached(cache, invalid_items):
    url = "https://fixture.invalid/invalid"
    with pytest.raises(TypeError, match="list of item dictionaries"):
        await IncrementalScraper(cache).scrape_incremental([url], AsyncMock(return_value=invalid_items))
    assert cache.should_scrape(url, 3600)[0] is True

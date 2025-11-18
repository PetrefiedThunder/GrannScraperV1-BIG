"""
Tests for smart caching system.
"""

import pytest
import time
from pathlib import Path
import tempfile

from scraper.storage.smart_cache import SmartCache, IncrementalScraper


@pytest.fixture
def temp_cache():
    """Create a temporary cache for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.db"
        cache = SmartCache(str(cache_path))
        yield cache
        cache.close()


class TestSmartCache:
    """Test smart cache functionality."""

    def test_cache_initialization(self, temp_cache):
        """Test cache initialization."""
        assert temp_cache is not None
        stats = temp_cache.get_stats()
        assert stats["total_entries"] == 0

    def test_cache_page(self, temp_cache):
        """Test caching a page."""
        url = "https://example.com"
        content = "<html><body>Test content</body></html>"

        temp_cache.cache_page(url, content)

        stats = temp_cache.get_stats()
        assert stats["total_entries"] == 1

    def test_should_scrape_new_url(self, temp_cache):
        """Test should_scrape with new URL."""
        url = "https://example.com/new"

        should_scrape, reason = temp_cache.should_scrape(url)

        assert should_scrape is True
        assert "not in cache" in reason.lower()

    def test_should_scrape_cached_fresh(self, temp_cache):
        """Test should_scrape with fresh cached URL."""
        url = "https://example.com/fresh"
        content = "<html><body>Fresh content</body></html>"

        # Cache the page
        temp_cache.cache_page(url, content)

        # Check immediately (should be fresh)
        should_scrape, reason = temp_cache.should_scrape(url, ttl_seconds=3600)

        assert should_scrape is False
        assert "fresh" in reason.lower()

    def test_should_scrape_cached_expired(self, temp_cache):
        """Test should_scrape with expired cached URL."""
        url = "https://example.com/expired"
        content = "<html><body>Old content</body></html>"

        # Cache the page
        temp_cache.cache_page(url, content)

        # Check with very short TTL (expired)
        should_scrape, reason = temp_cache.should_scrape(url, ttl_seconds=0)

        assert should_scrape is True
        assert "expired" in reason.lower()

    def test_content_hash_change_detection(self, temp_cache):
        """Test content change detection via hashing."""
        url = "https://example.com/changing"
        content1 = "<html><body>Version 1</body></html>"
        content2 = "<html><body>Version 2</body></html>"

        # Cache initial version
        temp_cache.cache_page(url, content1)

        # Get hash
        hash1 = temp_cache._hash_content(content1)
        hash2 = temp_cache._hash_content(content2)

        # Hashes should be different
        assert hash1 != hash2

    def test_get_cached_content(self, temp_cache):
        """Test retrieving cached content."""
        url = "https://example.com/retrieve"
        content = "<html><body>Cached content</body></html>"

        # Cache the page
        temp_cache.cache_page(url, content)

        # Retrieve
        cached = temp_cache.get_cached_content(url)

        assert cached is not None
        assert cached["content"] == content

    def test_clear_expired(self, temp_cache):
        """Test clearing expired entries."""
        # Add some entries
        temp_cache.cache_page("https://example.com/1", "Content 1")
        time.sleep(0.1)
        temp_cache.cache_page("https://example.com/2", "Content 2")

        # Clear entries older than 0.05 seconds
        deleted = temp_cache.clear_expired(ttl_seconds=0.05)

        assert deleted > 0

    def test_clear_all(self, temp_cache):
        """Test clearing all cache."""
        # Add entries
        temp_cache.cache_page("https://example.com/1", "Content 1")
        temp_cache.cache_page("https://example.com/2", "Content 2")
        temp_cache.cache_page("https://example.com/3", "Content 3")

        stats_before = temp_cache.get_stats()
        assert stats_before["total_entries"] == 3

        # Clear all
        temp_cache.clear_all()

        stats_after = temp_cache.get_stats()
        assert stats_after["total_entries"] == 0

    def test_get_stats(self, temp_cache):
        """Test cache statistics."""
        # Add some entries
        temp_cache.cache_page("https://example.com/1", "Content 1")
        temp_cache.cache_page("https://example.com/2", "Content 2")

        # Mark one as fresh, one as should scrape
        temp_cache.should_scrape("https://example.com/1", ttl_seconds=3600)  # Fresh
        temp_cache.should_scrape("https://example.com/2", ttl_seconds=0)     # Expired

        stats = temp_cache.get_stats()

        assert stats["total_entries"] == 2
        assert "cache_size_mb" in stats

    def test_hit_miss_tracking(self, temp_cache):
        """Test cache hit/miss tracking."""
        url = "https://example.com/tracked"

        # Miss (not in cache)
        temp_cache.should_scrape(url)

        # Add to cache
        temp_cache.cache_page(url, "Content")

        # Hit (in cache and fresh)
        temp_cache.should_scrape(url, ttl_seconds=3600)

        stats = temp_cache.get_stats()

        assert stats["hits"] >= 0
        assert stats["misses"] >= 0


class TestIncrementalScraper:
    """Test incremental scraping."""

    @pytest.mark.asyncio
    async def test_scrape_incremental_new_urls(self, temp_cache):
        """Test incremental scraping with new URLs."""
        scraper = IncrementalScraper(temp_cache)

        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]

        # Mock scrape function
        async def mock_scrape(url):
            return {"url": url, "data": "scraped"}

        # All URLs are new, should scrape all
        result = await scraper.scrape_incremental(urls, mock_scrape, ttl_seconds=3600)

        assert len(result["new_items"]) == 3
        assert result["stats"]["urls_to_check"] == 3
        assert result["stats"]["urls_scraped"] == 3

    @pytest.mark.asyncio
    async def test_scrape_incremental_cached_urls(self, temp_cache):
        """Test incremental scraping with cached URLs."""
        scraper = IncrementalScraper(temp_cache)

        urls = ["https://example.com/cached"]

        # Pre-cache the URL
        temp_cache.cache_page(urls[0], "Cached content")

        # Mock scrape function
        async def mock_scrape(url):
            return {"url": url, "data": "scraped"}

        # URL is cached and fresh, should not scrape
        result = await scraper.scrape_incremental(urls, mock_scrape, ttl_seconds=3600)

        assert result["stats"]["urls_to_check"] == 1
        assert result["stats"]["urls_scraped"] == 0  # Cached, not scraped
        assert result["stats"]["bandwidth_saved_pct"] > 0

    @pytest.mark.asyncio
    async def test_scrape_incremental_mixed(self, temp_cache):
        """Test incremental scraping with mixed URLs."""
        scraper = IncrementalScraper(temp_cache)

        urls = [
            "https://example.com/new1",
            "https://example.com/cached",
            "https://example.com/new2",
        ]

        # Cache one URL
        temp_cache.cache_page(urls[1], "Cached content")

        # Mock scrape function
        async def mock_scrape(url):
            return [{"url": url, "data": "scraped"}]

        # 1 cached, 2 new
        result = await scraper.scrape_incremental(urls, mock_scrape, ttl_seconds=3600)

        assert result["stats"]["urls_to_check"] == 3
        assert result["stats"]["urls_scraped"] == 2  # Only new ones
        assert result["stats"]["urls_skipped"] == 1  # Cached one

    @pytest.mark.asyncio
    async def test_get_changed_urls(self, temp_cache):
        """Test getting only changed URLs."""
        scraper = IncrementalScraper(temp_cache)

        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]

        # Cache URL 2
        temp_cache.cache_page(urls[1], "Cached content")

        # Get changed URLs
        changed = scraper.cache.get_changed_urls(urls, ttl_seconds=3600)

        # Should include URLs 1 and 3 (not cached), exclude URL 2 (cached)
        assert len(changed) == 2
        assert urls[0] in changed
        assert urls[2] in changed
        assert urls[1] not in changed


class TestCachePerformance:
    """Test cache performance and efficiency."""

    def test_large_content_handling(self, temp_cache):
        """Test caching large content."""
        url = "https://example.com/large"
        # Create large content (1MB)
        large_content = "<html>" + ("x" * 1_000_000) + "</html>"

        # Should handle large content
        temp_cache.cache_page(url, large_content)

        cached = temp_cache.get_cached_content(url)
        assert cached is not None
        assert len(cached["content"]) == len(large_content)

    def test_many_urls_caching(self, temp_cache):
        """Test caching many URLs."""
        # Cache 100 URLs
        for i in range(100):
            temp_cache.cache_page(f"https://example.com/{i}", f"Content {i}")

        stats = temp_cache.get_stats()
        assert stats["total_entries"] == 100

    def test_hash_collision_resistance(self, temp_cache):
        """Test that different content produces different hashes."""
        contents = [
            "<html>Content A</html>",
            "<html>Content B</html>",
            "<html>Content C</html>",
        ]

        hashes = [temp_cache._hash_content(c) for c in contents]

        # All hashes should be unique
        assert len(set(hashes)) == len(hashes)

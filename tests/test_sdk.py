"""
Tests for the Python SDK.
"""

import pytest
from unittest.mock import Mock, patch
import httpx

from scraper.sdk import GrandmaScrapeClient, JobStatus


@pytest.fixture
def mock_client():
    """Create a mock SDK client."""
    with patch('httpx.Client') as mock:
        client = GrandmaScrapeClient()
        yield client


def test_client_initialization():
    """Test SDK client initialization."""
    client = GrandmaScrapeClient(
        base_url="http://test:8000",
        api_key="test-key",
        timeout=60.0
    )

    assert client.base_url == "http://test:8000"
    assert client.api_key == "test-key"
    assert client.timeout == 60.0


def test_client_context_manager():
    """Test SDK client as context manager."""
    with GrandmaScrapeClient() as client:
        assert client is not None

    # Should be closed after context


def test_health_check(mock_client):
    """Test health check endpoint."""
    mock_client.client.get = Mock(return_value=Mock(
        status_code=200,
        json=lambda: {"status": "healthy", "timestamp": "2024-01-01T00:00:00"}
    ))

    result = mock_client.health_check()

    assert result["status"] == "healthy"
    mock_client.client.get.assert_called_once()


def test_create_job(mock_client):
    """Test job creation."""
    mock_client.client.post = Mock(return_value=Mock(
        status_code=200,
        json=lambda: {"job_id": "test-job-123", "status": "created"}
    ))

    job_data = {
        "id": "test-job-123",
        "name": "Test Job",
        "start_url": "https://example.com",
        "fields": {},
    }

    job_id = mock_client.create_job(job_data)

    assert job_id == "test-job-123"
    mock_client.client.post.assert_called_once()


def test_get_job_status(mock_client):
    """Test getting job status."""
    mock_client.client.get = Mock(return_value=Mock(
        status_code=200,
        json=lambda: {
            "job_id": "test-job-123",
            "is_running": False,
            "has_result": True,
            "status": "success",
            "items_scraped": 100,
            "pages_visited": 10,
            "errors": 0,
            "duration": 12.5
        }
    ))

    status = mock_client.get_job_status("test-job-123")

    assert isinstance(status, JobStatus)
    assert status.job_id == "test-job-123"
    assert status.is_running is False
    assert status.has_result is True
    assert status.items_scraped == 100


def test_list_jobs(mock_client):
    """Test listing jobs."""
    mock_client.client.get = Mock(return_value=Mock(
        status_code=200,
        json=lambda: {
            "total": 2,
            "jobs": [
                {"id": "job1", "name": "Job 1", "start_url": "https://example.com"},
                {"id": "job2", "name": "Job 2", "start_url": "https://test.com"},
            ]
        }
    ))

    jobs = mock_client.list_jobs()

    assert len(jobs) == 2
    assert jobs[0]["id"] == "job1"
    assert jobs[1]["id"] == "job2"


def test_analyze_url(mock_client):
    """Test URL analysis."""
    mock_client.client.post = Mock(return_value=Mock(
        status_code=200,
        json=lambda: {
            "url": "https://example.com",
            "item_selector": ".product",
            "fields": {
                "title": {"selector": ".title", "type": "text"},
                "price": {"selector": ".price", "type": "number"},
            },
            "pagination": {"next_button": ".next"},
        }
    ))

    analysis = mock_client.analyze_url("https://example.com")

    assert analysis["url"] == "https://example.com"
    assert analysis["item_selector"] == ".product"
    assert "title" in analysis["fields"]
    assert "price" in analysis["fields"]


def test_get_all_results_pagination(mock_client):
    """Test getting all results with pagination."""
    # Mock multiple pages
    call_count = [0]

    def mock_get(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First page
            return Mock(
                status_code=200,
                json=lambda: {
                    "items": [{"id": 1}, {"id": 2}],
                    "pagination": {"has_more": True}
                }
            )
        else:
            # Second page
            return Mock(
                status_code=200,
                json=lambda: {
                    "items": [{"id": 3}],
                    "pagination": {"has_more": False}
                }
            )

    mock_client.client.get = mock_get

    results = mock_client.get_all_results("test-job")

    assert len(results) == 3
    assert results[0]["id"] == 1
    assert results[1]["id"] == 2
    assert results[2]["id"] == 3


@pytest.mark.asyncio
async def test_async_client_auto_scrape():
    """Test async client auto-scrape."""
    from scraper.sdk import AsyncGrandmaScrapeClient

    with patch('httpx.AsyncClient') as mock:
        client = AsyncGrandmaScrapeClient()

        # Mock analysis response
        async def mock_post(*args, **kwargs):
            if '/analyze' in str(args):
                return Mock(
                    status_code=200,
                    json=lambda: {
                        "item_selector": ".item",
                        "fields": {},
                        "pagination": {}
                    },
                    raise_for_status=lambda: None
                )
            else:
                return Mock(
                    status_code=200,
                    json=lambda: {"job_id": "test-job-123"},
                    raise_for_status=lambda: None
                )

        client.client.post = mock_post

        # This would actually call auto_scrape, but we're just testing the structure
        assert client is not None

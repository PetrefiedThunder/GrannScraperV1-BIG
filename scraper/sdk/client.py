"""
Python SDK for GrandmaScrape API.

Provides a clean, pythonic interface to the REST API.

Usage:
    from scraper.sdk import GrandmaScrapeClient

    client = GrandmaScrapeClient("http://localhost:8000")

    # Auto-detect and scrape
    job_id = client.auto_scrape("https://example.com", export_format="csv")

    # Wait for completion
    result = client.wait_for_job(job_id)

    # Get results
    data = client.get_results(job_id)
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import httpx
from pydantic import BaseModel

from scraper.config.models import ScrapeJob, ScrapeResult


class JobStatus(BaseModel):
    """Job execution status."""
    job_id: str
    is_running: bool
    has_result: bool
    status: Optional[str] = None
    items_scraped: Optional<int> = None
    pages_visited: Optional[int] = None
    errors: Optional[int] = None
    duration: Optional[float] = None


class GrandmaScrapeClient:
    """
    Python SDK for GrandmaScrape API.

    Provides high-level methods for:
    - Auto-detection and scraping
    - Job management
    - Result retrieval
    - Workflow creation
    - Data quality analysis
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize SDK client.

        Args:
            base_url: API server base URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout
        )

        self.async_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close HTTP clients."""
        self.client.close()

    async def aclose(self):
        """Close async HTTP client."""
        await self.async_client.aclose()

    # ============================================================================
    # HIGH-LEVEL METHODS (Grandma-simple!)
    # ============================================================================

    def auto_scrape(
        self,
        url: str,
        max_pages: int = 10,
        export_format: str = "json",
        concurrent: bool = True,
        wait: bool = False
    ) -> str:
        """
        Auto-detect structure and scrape (GRANDMA-SIMPLE!).

        Args:
            url: URL to scrape
            max_pages: Maximum pages to scrape
            export_format: Export format (json, csv, excel)
            concurrent: Use concurrent scraping
            wait: Wait for completion

        Returns:
            Job ID
        """
        # Auto-detect structure
        analysis = self.analyze_url(url)

        # Create job from analysis
        job = ScrapeJob(
            name=f"Auto-scraped: {url}",
            start_url=url,
            item_selector=analysis.get('item_selector'),
            fields=analysis.get('fields', {}),
            pagination=analysis.get('pagination', {}),
            max_pages=max_pages,
            export={'format': export_format}
        )

        # Create and run job
        job_id = self.create_job(job)
        self.run_job(job_id, concurrent=concurrent)

        if wait:
            self.wait_for_job(job_id)

        return job_id

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None
    ) -> JobStatus:
        """
        Wait for job to complete.

        Args:
            job_id: Job ID
            poll_interval: Seconds between status checks
            timeout: Max seconds to wait

        Returns:
            Final job status
        """
        start_time = time.time()

        while True:
            status = self.get_job_status(job_id)

            if not status.is_running:
                return status

            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

            time.sleep(poll_interval)

    # ============================================================================
    # JOB MANAGEMENT
    # ============================================================================

    def create_job(self, job: Union[ScrapeJob, Dict[str, Any]]) -> str:
        """
        Create a scraping job.

        Args:
            job: ScrapeJob object or dict

        Returns:
            Job ID
        """
        if isinstance(job, ScrapeJob):
            job_data = job.model_dump()
        else:
            job_data = job

        response = self.client.post(
            '/api/v1/jobs',
            json={'job': job_data}
        )
        response.raise_for_status()

        return response.json()['job_id']

    def list_jobs(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all jobs.

        Args:
            enabled_only: Only show enabled jobs

        Returns:
            List of jobs
        """
        response = self.client.get(
            '/api/v1/jobs',
            params={'enabled_only': enabled_only}
        )
        response.raise_for_status()

        return response.json()['jobs']

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """
        Get job details.

        Args:
            job_id: Job ID

        Returns:
            Job details
        """
        response = self.client.get(f'/api/v1/jobs/{job_id}')
        response.raise_for_status()

        return response.json()

    def delete_job(self, job_id: str):
        """
        Delete a job.

        Args:
            job_id: Job ID
        """
        response = self.client.delete(f'/api/v1/jobs/{job_id}')
        response.raise_for_status()

    def run_job(
        self,
        job_id: str,
        concurrent: bool = False,
        incremental: bool = False
    ) -> Dict[str, Any]:
        """
        Run a scraping job.

        Args:
            job_id: Job ID
            concurrent: Use concurrent scraping
            incremental: Use incremental scraping

        Returns:
            Execution status
        """
        response = self.client.post(
            f'/api/v1/jobs/{job_id}/run',
            params={
                'concurrent': concurrent,
                'incremental': incremental
            }
        )
        response.raise_for_status()

        return response.json()

    def get_job_status(self, job_id: str) -> JobStatus:
        """
        Get job execution status.

        Args:
            job_id: Job ID

        Returns:
            Job status
        """
        response = self.client.get(f'/api/v1/jobs/{job_id}/status')
        response.raise_for_status()

        return JobStatus(**response.json())

    def get_results(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get job results with pagination.

        Args:
            job_id: Job ID
            limit: Max items to return
            offset: Offset for pagination

        Returns:
            Results data
        """
        response = self.client.get(
            f'/api/v1/jobs/{job_id}/results',
            params={'limit': limit, 'offset': offset}
        )
        response.raise_for_status()

        return response.json()

    def get_all_results(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all results for a job (handles pagination).

        Args:
            job_id: Job ID

        Returns:
            All items
        """
        all_items = []
        offset = 0
        limit = 1000

        while True:
            response = self.get_results(job_id, limit=limit, offset=offset)
            items = response['items']
            all_items.extend(items)

            if not response['pagination']['has_more']:
                break

            offset += limit

        return all_items

    # ============================================================================
    # SMART FEATURES
    # ============================================================================

    def analyze_url(self, url: str, max_pages: int = 1) -> Dict[str, Any]:
        """
        Analyze URL and auto-detect structure.

        Args:
            url: URL to analyze
            max_pages: Max pages to analyze

        Returns:
            Detected structure
        """
        response = self.client.post(
            '/api/v1/analyze',
            json={'url': url, 'max_pages': max_pages}
        )
        response.raise_for_status()

        return response.json()

    def check_data_quality(self, job_id: str) -> Dict[str, Any]:
        """
        Run data quality analysis.

        Args:
            job_id: Job ID

        Returns:
            Quality report
        """
        response = self.client.post(f'/api/v1/jobs/{job_id}/quality-check')
        response.raise_for_status()

        return response.json()

    def detect_anomalies(self, job_id: str) -> Dict[str, Any]:
        """
        Detect anomalies in job results.

        Args:
            job_id: Job ID

        Returns:
            Anomaly report
        """
        response = self.client.post(f'/api/v1/jobs/{job_id}/detect-anomalies')
        response.raise_for_status()

        return response.json()

    # ============================================================================
    # WORKFLOWS
    # ============================================================================

    def create_workflow(
        self,
        name: str,
        nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a workflow.

        Args:
            name: Workflow name
            nodes: Workflow nodes

        Returns:
            Workflow info
        """
        response = self.client.post(
            '/api/v1/workflows',
            json={'name': name, 'nodes': nodes}
        )
        response.raise_for_status()

        return response.json()

    def list_workflows(self) -> List[Dict[str, Any]]:
        """
        List all workflows.

        Returns:
            List of workflows
        """
        response = self.client.get('/api/v1/workflows')
        response.raise_for_status()

        return response.json()['workflows']

    def get_workflow(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get workflow details.

        Args:
            workflow_name: Workflow name

        Returns:
            Workflow details
        """
        response = self.client.get(f'/api/v1/workflows/{workflow_name}')
        response.raise_for_status()

        return response.json()

    # ============================================================================
    # CACHE MANAGEMENT
    # ============================================================================

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache stats
        """
        response = self.client.get('/api/v1/cache/stats')
        response.raise_for_status()

        return response.json()

    def clear_cache(
        self,
        expired_only: bool = False,
        ttl_seconds: int = 3600
    ) -> Dict[str, Any]:
        """
        Clear cache.

        Args:
            expired_only: Only clear expired entries
            ttl_seconds: TTL for expired check

        Returns:
            Clear result
        """
        response = self.client.delete(
            '/api/v1/cache',
            params={
                'expired_only': expired_only,
                'ttl_seconds': ttl_seconds
            }
        )
        response.raise_for_status()

        return response.json()

    # ============================================================================
    # HEALTH & INFO
    # ============================================================================

    def health_check(self) -> Dict[str, str]:
        """
        Check API health.

        Returns:
            Health status
        """
        response = self.client.get('/api/v1/health')
        response.raise_for_status()

        return response.json()

    def get_info(self) -> Dict[str, Any]:
        """
        Get API information and statistics.

        Returns:
            API info
        """
        response = self.client.get('/api/v1/info')
        response.raise_for_status()

        return response.json()


# ============================================================================
# ASYNC CLIENT
# ============================================================================

class AsyncGrandmaScrapeClient:
    """
    Async Python SDK for GrandmaScrape API.

    Same interface as GrandmaScrapeClient but fully async.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def auto_scrape(
        self,
        url: str,
        max_pages: int = 10,
        export_format: str = "json",
        concurrent: bool = True,
        wait: bool = False
    ) -> str:
        """Auto-detect and scrape (async)."""
        analysis = await self.analyze_url(url)

        job = ScrapeJob(
            name=f"Auto-scraped: {url}",
            start_url=url,
            item_selector=analysis.get('item_selector'),
            fields=analysis.get('fields', {}),
            pagination=analysis.get('pagination', {}),
            max_pages=max_pages,
            export={'format': export_format}
        )

        job_id = await self.create_job(job)
        await self.run_job(job_id, concurrent=concurrent)

        if wait:
            await self.wait_for_job(job_id)

        return job_id

    async def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None
    ) -> JobStatus:
        """Wait for job to complete (async)."""
        start_time = time.time()

        while True:
            status = await self.get_job_status(job_id)

            if not status.is_running:
                return status

            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

            await asyncio.sleep(poll_interval)

    async def create_job(self, job: Union[ScrapeJob, Dict[str, Any]]) -> str:
        """Create job (async)."""
        if isinstance(job, ScrapeJob):
            job_data = job.model_dump()
        else:
            job_data = job

        response = await self.client.post('/api/v1/jobs', json={'job': job_data})
        response.raise_for_status()

        return response.json()['job_id']

    async def run_job(
        self,
        job_id: str,
        concurrent: bool = False,
        incremental: bool = False
    ) -> Dict[str, Any]:
        """Run job (async)."""
        response = await self.client.post(
            f'/api/v1/jobs/{job_id}/run',
            params={'concurrent': concurrent, 'incremental': incremental}
        )
        response.raise_for_status()

        return response.json()

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get job status (async)."""
        response = await self.client.get(f'/api/v1/jobs/{job_id}/status')
        response.raise_for_status()

        return JobStatus(**response.json())

    async def get_all_results(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all results (async)."""
        all_items = []
        offset = 0
        limit = 1000

        while True:
            response = await self.client.get(
                f'/api/v1/jobs/{job_id}/results',
                params={'limit': limit, 'offset': offset}
            )
            response.raise_for_status()

            data = response.json()
            items = data['items']
            all_items.extend(items)

            if not data['pagination']['has_more']:
                break

            offset += limit

        return all_items

    async def analyze_url(self, url: str, max_pages: int = 1) -> Dict[str, Any]:
        """Analyze URL (async)."""
        response = await self.client.post(
            '/api/v1/analyze',
            json={'url': url, 'max_pages': max_pages}
        )
        response.raise_for_status()

        return response.json()

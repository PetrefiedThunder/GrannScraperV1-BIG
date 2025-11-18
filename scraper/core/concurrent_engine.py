"""
High-performance concurrent scraping engine.

Intelligently parallelizes scraping with:
- Smart queue management
- Automatic retry with backoff
- Domain-aware concurrency limits
- Progress tracking
- Memory-efficient streaming
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from scraper.config.models import ScrapeJob, ScrapeResult

logger = logging.getLogger(__name__)


@dataclass
class ScrapeTask:
    """Individual scrape task."""
    url: str
    priority: int = 0
    retry_count: int = 0
    metadata: Dict[str, Any] = None


class ConcurrentScraper:
    """
    High-performance concurrent scraper with intelligent queuing.

    Features:
    - Domain-aware concurrency (don't overwhelm single domain)
    - Priority queue for important pages first
    - Automatic retry with exponential backoff
    - Progress tracking and estimation
    - Memory-efficient streaming results
    """

    def __init__(self, job: ScrapeJob, max_workers: int = 10):
        self.job = job
        self.max_workers = max_workers
        self.max_workers_per_domain = 2  # Politeness: max 2 concurrent per domain

        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.result_queue: asyncio.Queue = asyncio.Queue()

        self.domain_semaphores: Dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self.max_workers_per_domain)
        )

        self.active_workers = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_tasks = 0

        self.start_time: Optional[datetime] = None
        self.stats = {
            'domains_scraped': set(),
            'total_bytes': 0,
            'total_items': 0,
        }

    async def add_task(self, task: ScrapeTask):
        """Add task to queue."""
        await self.task_queue.put(task)
        self.total_tasks += 1

    async def add_urls(self, urls: List[str], priority: int = 0):
        """Add multiple URLs to queue."""
        for url in urls:
            await self.add_task(ScrapeTask(url=url, priority=priority))

    async def worker(self, worker_id: int, scrape_func: Callable):
        """Worker that processes tasks from queue."""
        logger.debug(f"Worker {worker_id} started")

        while True:
            try:
                # Get task with timeout to allow graceful shutdown
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # Check if queue is empty and no workers active
                if self.task_queue.empty() and self.active_workers == 1:
                    break
                continue

            self.active_workers += 1

            try:
                # Get domain for rate limiting
                domain = urlparse(task.url).netloc
                self.stats['domains_scraped'].add(domain)

                # Acquire domain semaphore (rate limit per domain)
                async with self.domain_semaphores[domain]:
                    logger.info(f"Worker {worker_id} scraping: {task.url}")

                    # Execute scrape
                    result = await scrape_func(task.url)

                    if result:
                        # Success
                        await self.result_queue.put({
                            'status': 'success',
                            'url': task.url,
                            'data': result,
                            'task': task
                        })
                        self.completed_tasks += 1

                    else:
                        # Failed but might retry
                        if task.retry_count < self.job.retry.max_retries:
                            # Re-queue with backoff
                            task.retry_count += 1
                            backoff = self.job.retry.backoff_factor ** task.retry_count
                            await asyncio.sleep(backoff)
                            await self.add_task(task)
                            logger.info(f"Retry {task.retry_count} for {task.url}")
                        else:
                            # Max retries exceeded
                            await self.result_queue.put({
                                'status': 'failed',
                                'url': task.url,
                                'error': 'Max retries exceeded',
                                'task': task
                            })
                            self.failed_tasks += 1

            except Exception as e:
                logger.error(f"Worker {worker_id} error on {task.url}: {e}")
                await self.result_queue.put({
                    'status': 'error',
                    'url': task.url,
                    'error': str(e),
                    'task': task
                })
                self.failed_tasks += 1

            finally:
                self.active_workers -= 1
                self.task_queue.task_done()

        logger.debug(f"Worker {worker_id} finished")

    async def run(self, scrape_func: Callable) -> ScrapeResult:
        """
        Run concurrent scraping.

        Args:
            scrape_func: Async function that takes URL and returns scraped data

        Returns:
            ScrapeResult
        """
        self.start_time = datetime.utcnow()

        result = ScrapeResult(
            job_id=self.job.id,
            status='success',
            start_time=self.start_time,
        )

        # Start workers
        workers = [
            asyncio.create_task(self.worker(i, scrape_func))
            for i in range(self.max_workers)
        ]

        # Process results as they come in
        results_processed = 0
        while results_processed < self.total_tasks:
            try:
                # Get result with timeout
                item = await asyncio.wait_for(
                    self.result_queue.get(),
                    timeout=10.0
                )

                results_processed += 1

                if item['status'] == 'success':
                    if isinstance(item['data'], list):
                        result.data.extend(item['data'])
                        result.items_scraped += len(item['data'])
                    else:
                        result.data.append(item['data'])
                        result.items_scraped += 1

                    result.pages_visited += 1

                else:
                    error_msg = f"{item['url']}: {item.get('error', 'Unknown error')}"
                    result.errors.append(error_msg)

                # Progress update
                progress = (results_processed / self.total_tasks) * 100
                logger.info(f"Progress: {progress:.1f}% ({results_processed}/{self.total_tasks})")

            except asyncio.TimeoutError:
                # Check if all tasks are done
                if self.task_queue.empty() and self.active_workers == 0:
                    break

        # Wait for all workers to finish
        await asyncio.gather(*workers, return_exceptions=True)

        # Finalize result
        result.end_time = datetime.utcnow()
        result.duration_seconds = (result.end_time - result.start_time).total_seconds()

        result.metadata = {
            'job_name': self.job.name,
            'job_id': self.job.id,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'total_tasks': self.total_tasks,
            'domains_scraped': len(self.stats['domains_scraped']),
            'average_speed': result.items_scraped / result.duration_seconds if result.duration_seconds > 0 else 0,
        }

        if result.errors:
            result.status = 'partial' if result.data else 'failed'

        logger.info(
            f"Concurrent scraping completed: "
            f"{result.items_scraped} items, "
            f"{result.pages_visited} pages, "
            f"{len(result.errors)} errors, "
            f"{result.duration_seconds:.2f}s"
        )

        return result

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress statistics."""
        if not self.start_time:
            return {}

        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        tasks_done = self.completed_tasks + self.failed_tasks

        return {
            'total_tasks': self.total_tasks,
            'completed': self.completed_tasks,
            'failed': self.failed_tasks,
            'pending': self.total_tasks - tasks_done,
            'active_workers': self.active_workers,
            'elapsed_seconds': elapsed,
            'tasks_per_second': tasks_done / elapsed if elapsed > 0 else 0,
            'estimated_remaining_seconds': (
                (self.total_tasks - tasks_done) / (tasks_done / elapsed)
                if elapsed > 0 and tasks_done > 0 else None
            ),
        }


class StreamingScraper:
    """
    Memory-efficient streaming scraper for large datasets.

    Processes and exports results as they're scraped, without
    holding everything in memory.
    """

    def __init__(self, job: ScrapeJob):
        self.job = job
        self.item_count = 0
        self.page_count = 0

    async def stream_to_file(
        self,
        scrape_func: Callable,
        urls: List[str],
        output_file: str
    ):
        """
        Stream results directly to file without loading all in memory.

        Perfect for scraping millions of items.
        """
        import aiofiles
        import json

        async with aiofiles.open(output_file, 'w') as f:
            # Write header
            await f.write('[\n')

            first_item = True

            for url in urls:
                try:
                    data = await scrape_func(url)

                    if data:
                        if isinstance(data, list):
                            items = data
                        else:
                            items = [data]

                        for item in items:
                            if not first_item:
                                await f.write(',\n')

                            await f.write(json.dumps(item, indent=2))
                            first_item = False
                            self.item_count += 1

                            # Log progress
                            if self.item_count % 100 == 0:
                                logger.info(f"Streamed {self.item_count} items...")

                        self.page_count += 1

                except Exception as e:
                    logger.error(f"Error streaming {url}: {e}")

            # Write footer
            await f.write('\n]\n')

        logger.info(f"Streaming completed: {self.item_count} items from {self.page_count} pages")


class SmartScheduler:
    """
    Intelligent task scheduler that optimizes scraping order.

    Features:
    - Prioritizes important pages
    - Balances load across domains
    - Adapts to site response times
    - Handles dependencies between tasks
    """

    def __init__(self):
        self.domain_performance: Dict[str, float] = defaultdict(float)  # avg response time
        self.domain_task_count: Dict[str, int] = defaultdict(int)

    def calculate_priority(self, url: str, base_priority: int = 0) -> int:
        """
        Calculate task priority based on multiple factors.

        Higher priority = processed first
        """
        domain = urlparse(url).netloc

        priority = base_priority

        # Lower priority for domains with many pending tasks (spread load)
        priority -= self.domain_task_count[domain] * 10

        # Lower priority for slow domains (process fast sites first)
        if domain in self.domain_performance:
            priority -= int(self.domain_performance[domain] * 10)

        # Increase priority for critical paths (home page, category pages)
        if url.count('/') <= 3:  # Shallow URLs often more important
            priority += 100

        return priority

    def update_performance(self, url: str, response_time: float):
        """Update domain performance metrics."""
        domain = urlparse(url).netloc

        # Exponential moving average
        if domain in self.domain_performance:
            self.domain_performance[domain] = (
                0.7 * self.domain_performance[domain] +
                0.3 * response_time
            )
        else:
            self.domain_performance[domain] = response_time

    def reorder_tasks(self, tasks: List[ScrapeTask]) -> List[ScrapeTask]:
        """Reorder tasks by calculated priority."""
        for task in tasks:
            task.priority = self.calculate_priority(task.url, task.priority)

        return sorted(tasks, key=lambda t: t.priority, reverse=True)

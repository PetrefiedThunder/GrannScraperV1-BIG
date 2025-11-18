"""
Full-featured REST API server.

Expose all scraping capabilities via REST API for:
- Remote job management
- Programmatic access
- Integration with other systems
- Web dashboard backend
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scraper.config.models import ScrapeJob, ScrapeResult
from scraper.core.engine import ScraperEngine
from scraper.core.concurrent_engine import ConcurrentScraper
from scraper.export.export_manager import ExportManager
from scraper.ml.data_intelligence import DataQualityAnalyzer, AnomalyDetector
from scraper.storage.smart_cache import SmartCache, IncrementalScraper
from scraper.scheduler.workflow_dag import WorkflowDAG, WorkflowBuilder

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="GrandmaScrape API",
    description="Enterprise web scraping API - grandma-simple, enterprise-grade",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web dashboard
static_path = Path(__file__).parent.parent / "web" / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# In-memory storage (use database in production)
jobs_db: Dict[str, ScrapeJob] = {}
results_db: Dict[str, ScrapeResult] = {}
workflows_db: Dict[str, WorkflowDAG] = {}
running_jobs: Dict[str, asyncio.Task] = {}


# Request/Response models
class JobCreateRequest(BaseModel):
    """Request to create a new scraping job."""
    job: ScrapeJob


class JobRunRequest(BaseModel):
    """Request to run a job."""
    job_id: str
    concurrent: bool = False
    incremental: bool = False


class WorkflowCreateRequest(BaseModel):
    """Request to create a workflow."""
    name: str
    nodes: List[Dict[str, Any]]


class AnalyzeRequest(BaseModel):
    """Request to analyze a URL."""
    url: str
    max_pages: int = 1


# ============================================================================
# JOB MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/v1/jobs")
async def create_job(request: JobCreateRequest) -> Dict[str, Any]:
    """
    Create a new scraping job.

    Returns job ID.
    """
    job = request.job

    if job.id in jobs_db:
        raise HTTPException(status_code=400, detail="Job ID already exists")

    jobs_db[job.id] = job

    logger.info(f"Created job: {job.id}")

    return {
        "job_id": job.id,
        "status": "created",
        "message": f"Job {job.name} created successfully"
    }


@app.get("/api/v1/jobs")
async def list_jobs(
    enabled_only: bool = Query(False, description="Only show enabled jobs")
) -> Dict[str, Any]:
    """
    List all jobs.

    Returns list of jobs with metadata.
    """
    jobs = list(jobs_db.values())

    if enabled_only:
        jobs = [j for j in jobs if j.enabled]

    return {
        "total": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "start_url": job.start_url,
                "enabled": job.enabled,
                "created_at": job.created_at.isoformat(),
            }
            for job in jobs
        ]
    }


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str) -> ScrapeJob:
    """Get job details."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    return jobs_db[job_id]


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str) -> Dict[str, str]:
    """Delete a job."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    # Cancel if running
    if job_id in running_jobs:
        running_jobs[job_id].cancel()
        del running_jobs[job_id]

    del jobs_db[job_id]

    logger.info(f"Deleted job: {job_id}")

    return {"status": "deleted", "job_id": job_id}


# ============================================================================
# JOB EXECUTION ENDPOINTS
# ============================================================================

@app.post("/api/v1/jobs/{job_id}/run")
async def run_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    concurrent: bool = Query(False, description="Use concurrent scraping"),
    incremental: bool = Query(False, description="Use incremental scraping")
) -> Dict[str, Any]:
    """
    Run a scraping job.

    Returns immediately with job status. Use /results endpoint to get results.
    """
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_id in running_jobs:
        raise HTTPException(status_code=400, detail="Job already running")

    job = jobs_db[job_id]

    # Start job in background
    task = asyncio.create_task(
        _execute_job(job_id, job, concurrent, incremental)
    )
    running_jobs[job_id] = task

    logger.info(f"Started job: {job_id} (concurrent={concurrent}, incremental={incremental})")

    return {
        "job_id": job_id,
        "status": "running",
        "message": f"Job {job.name} started",
        "concurrent": concurrent,
        "incremental": incremental
    }


async def _execute_job(
    job_id: str,
    job: ScrapeJob,
    concurrent: bool,
    incremental: bool
) -> ScrapeResult:
    """Execute a job (called in background)."""
    try:
        if incremental:
            # Incremental scraping
            cache = SmartCache()
            incremental_scraper = IncrementalScraper(cache)

            # Get URLs to scrape
            from scraper.core.engine import ScraperEngine
            engine = ScraperEngine()
            urls = await engine._generate_urls(job)

            # Scrape incrementally
            result_data = await incremental_scraper.scrape_incremental(
                urls,
                lambda url: engine.run_job(job),
                ttl_seconds=3600
            )

            # Convert to ScrapeResult
            result = ScrapeResult(
                job_id=job_id,
                status="success",
                items_scraped=len(result_data['new_items']),
                pages_visited=result_data['stats']['urls_scraped'],
                data=result_data['new_items'],
                metadata=result_data['stats']
            )

        elif concurrent:
            # Concurrent scraping
            concurrent_scraper = ConcurrentScraper(job, max_workers=10)

            # Add URLs
            from scraper.core.engine import ScraperEngine
            engine = ScraperEngine()
            urls = await engine._generate_urls(job)
            await concurrent_scraper.add_urls(urls)

            # Execute
            async def scrape_single(url):
                temp_job = ScrapeJob(
                    name=job.name,
                    start_url=url,
                    item_selector=job.item_selector,
                    fields=job.fields,
                )
                r = await engine.run_job(temp_job)
                return r.data

            result = await concurrent_scraper.run(scrape_single)

        else:
            # Standard scraping
            engine = ScraperEngine()
            result = await engine.run_job(job)

        # Store result
        results_db[job_id] = result

        # Export
        export_manager = ExportManager(job.export)
        await export_manager.export_result(result)

        return result

    finally:
        # Remove from running jobs
        if job_id in running_jobs:
            del running_jobs[job_id]


@app.get("/api/v1/jobs/{job_id}/status")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get job execution status."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    is_running = job_id in running_jobs
    has_result = job_id in results_db

    status = {
        "job_id": job_id,
        "is_running": is_running,
        "has_result": has_result,
    }

    if has_result:
        result = results_db[job_id]
        status.update({
            "status": result.status,
            "items_scraped": result.items_scraped,
            "pages_visited": result.pages_visited,
            "errors": len(result.errors),
            "duration": result.duration_seconds,
        })

    return status


@app.get("/api/v1/jobs/{job_id}/results")
async def get_job_results(
    job_id: str,
    limit: int = Query(100, description="Max items to return"),
    offset: int = Query(0, description="Offset for pagination")
) -> Dict[str, Any]:
    """Get job results with pagination."""
    if job_id not in results_db:
        raise HTTPException(status_code=404, detail="No results found")

    result = results_db[job_id]

    return {
        "job_id": job_id,
        "status": result.status,
        "total_items": result.items_scraped,
        "pages_visited": result.pages_visited,
        "errors": result.errors,
        "items": result.data[offset:offset + limit],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(result.data)
        }
    }


# ============================================================================
# SMART FEATURES ENDPOINTS
# ============================================================================

@app.post("/api/v1/analyze")
async def analyze_url(request: AnalyzeRequest) -> Dict[str, Any]:
    """
    Analyze a URL and auto-detect structure.

    Returns detected selectors, fields, and pagination.
    """
    from scraper.config.models import ScrapeJob
    from scraper.core.fetcher_static import StaticFetcher
    from scraper.strategies.intelligent_extraction import (
        IntelligentExtractor,
        SmartPaginationDetector
    )

    # Fetch page
    temp_job = ScrapeJob(name="analysis", start_url=request.url)

    async with StaticFetcher(temp_job) as fetcher:
        soup, html = await fetcher.fetch(request.url)

        if not soup:
            raise HTTPException(status_code=400, detail="Failed to fetch URL")

    # Auto-detect
    extractor = IntelligentExtractor()
    pagination_detector = SmartPaginationDetector()

    item_selector = await extractor.auto_detect_item_container(soup)
    detected_fields = await extractor.auto_detect_fields(
        soup,
        item_selector or "body"
    )
    pagination_config = await pagination_detector.detect_pagination(soup, request.url)

    return {
        "url": request.url,
        "item_selector": item_selector,
        "fields": detected_fields,
        "pagination": pagination_config,
        "analysis": {
            "html_size": len(html),
            "links": len(soup.find_all('a')),
            "images": len(soup.find_all('img')),
            "title": soup.title.string if soup.title else None
        }
    }


@app.post("/api/v1/jobs/{job_id}/quality-check")
async def check_data_quality(job_id: str) -> Dict[str, Any]:
    """
    Run data quality analysis on job results.

    Returns quality score and recommendations.
    """
    if job_id not in results_db:
        raise HTTPException(status_code=404, detail="No results found")

    result = results_db[job_id]

    analyzer = DataQualityAnalyzer()
    quality_report = analyzer.analyze_dataset(result.data)

    return {
        "job_id": job_id,
        "quality_report": quality_report
    }


@app.post("/api/v1/jobs/{job_id}/detect-anomalies")
async def detect_anomalies(job_id: str) -> Dict[str, Any]:
    """
    Detect anomalies in job results compared to baseline.

    Useful for monitoring if site structure changed.
    """
    if job_id not in results_db:
        raise HTTPException(status_code=404, detail="No results found")

    result = results_db[job_id]

    detector = AnomalyDetector()
    anomaly_report = detector.detect_anomalies(result.data)

    return {
        "job_id": job_id,
        "anomaly_report": anomaly_report
    }


# ============================================================================
# WORKFLOW ENDPOINTS
# ============================================================================

@app.post("/api/v1/workflows")
async def create_workflow(request: WorkflowCreateRequest) -> Dict[str, Any]:
    """Create a new workflow."""
    from scraper.scheduler.workflow_dag import WorkflowNode

    workflow = WorkflowDAG(request.name)

    for node_data in request.nodes:
        node = WorkflowNode(**node_data)
        workflow.add_node(node)

    workflow.build()

    workflows_db[request.name] = workflow

    return {
        "workflow_name": request.name,
        "nodes": len(workflow.nodes),
        "execution_levels": len(workflow.execution_order),
        "status": "created"
    }


@app.get("/api/v1/workflows")
async def list_workflows() -> Dict[str, Any]:
    """List all workflows."""
    return {
        "total": len(workflows_db),
        "workflows": [
            {
                "name": name,
                "nodes": len(workflow.nodes),
                "levels": len(workflow.execution_order)
            }
            for name, workflow in workflows_db.items()
        ]
    }


@app.get("/api/v1/workflows/{workflow_name}")
async def get_workflow(workflow_name: str) -> Dict[str, Any]:
    """Get workflow details."""
    if workflow_name not in workflows_db:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows_db[workflow_name]

    return {
        "name": workflow.name,
        "nodes": {
            node_id: {
                "type": node.type,
                "depends_on": node.depends_on,
                "status": node.status.value
            }
            for node_id, node in workflow.nodes.items()
        },
        "execution_plan": workflow.get_execution_plan()
    }


# ============================================================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    cache = SmartCache()
    return cache.get_stats()


@app.delete("/api/v1/cache")
async def clear_cache(
    expired_only: bool = Query(False, description="Only clear expired entries"),
    ttl_seconds: int = Query(3600, description="TTL for expired check")
) -> Dict[str, Any]:
    """Clear cache."""
    cache = SmartCache()

    if expired_only:
        deleted = cache.clear_expired(ttl_seconds)
        return {"status": "cleared", "expired_entries_deleted": deleted}
    else:
        cache.clear_all()
        return {"status": "cleared", "message": "All cache cleared"}


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/api/v1/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/v1/info")
async def get_info() -> Dict[str, Any]:
    """Get API information and statistics."""
    return {
        "version": "1.0.0",
        "name": "GrandmaScrape API",
        "statistics": {
            "total_jobs": len(jobs_db),
            "running_jobs": len(running_jobs),
            "completed_jobs": len(results_db),
            "workflows": len(workflows_db)
        },
        "features": [
            "auto_detection",
            "concurrent_scraping",
            "incremental_scraping",
            "data_quality_analysis",
            "anomaly_detection",
            "workflow_dag",
            "smart_caching"
        ]
    }


# ============================================================================
# WEB DASHBOARD
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the web dashboard."""
    index_path = Path(__file__).parent.parent / "web" / "static" / "index.html"

    if index_path.exists():
        return FileResponse(index_path)
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>GrandmaScrape API</title></head>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1>GrandmaScrape API</h1>
                    <p>API is running!</p>
                    <p>Dashboard not found. Please check web/static/index.html</p>
                    <p><a href="/docs">View API Documentation</a></p>
                </body>
            </html>
            """,
            status_code=200
        )


# ============================================================================
# RUN SERVER
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server."""
    import uvicorn

    logger.info(f"Starting GrandmaScrape API server on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()

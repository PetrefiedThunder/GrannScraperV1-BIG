"""Offline security contracts. Known defects stay strict-xfail until repaired.

Run with pytest-socket: --disable-socket --allow-unix-socket. All HTTP uses
ASGITransport or MockTransport. File proofs modify only pytest tmp_path data.
"""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from scraper.api import rest_server as api
from scraper.config.models import PaginationConfig, ScrapeJob, ScrapeResult
from scraper.core import engine as engine_module
from scraper.core import fetcher_static
from scraper.security.auth import RateLimiter as APIRateLimiter


@pytest.fixture(autouse=True)
def isolated_api_state(monkeypatch):
    """Replace globals instead of mutating state owned by another test."""
    monkeypatch.setattr(api, "jobs_db", {})
    monkeypatch.setattr(api, "results_db", {})
    monkeypatch.setattr(api, "workflows_db", {})
    monkeypatch.setattr(api, "running_jobs", {})
    monkeypatch.setattr(api, "jobs_lock", asyncio.Lock())
    monkeypatch.setattr(
        fetcher_static, "UserAgent", lambda: SimpleNamespace(random="qa", chrome="qa")
    )


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api.app), base_url="http://qa.test"
    ) as http_client:
        yield http_client


@pytest.mark.parametrize("identity", ["anonymous", "invalid"])
@pytest.mark.parametrize("operation", ["create", "list", "detail", "results", "delete"])
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-010: privileged API routes have no auth dependency",
)
async def test_api_rejects_unauthenticated_job_access(client, identity, operation):
    job = ScrapeJob(id="qa_boundary", name="QA fixture", start_url="https://example.test")
    api.jobs_db[job.id] = job
    api.results_db[job.id] = ScrapeResult(job_id=job.id, status="success")
    headers = {} if identity == "anonymous" else {"Authorization": "Bearer qa-invalid"}
    method, path, body = {
        "create": (
            "POST",
            "/api/v1/jobs",
            {"job": {"id": "qa_new", "name": "Fixture", "start_url": "https://example.test"}},
        ),
        "list": ("GET", "/api/v1/jobs", None),
        "detail": ("GET", f"/api/v1/jobs/{job.id}", None),
        "results": ("GET", f"/api/v1/jobs/{job.id}/results", None),
        "delete": ("DELETE", f"/api/v1/jobs/{job.id}", None),
    }[operation]
    response = await client.request(method, path, json=body, headers=headers)
    assert response.status_code in (401, 403)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-010: OpenAPI declares no security on job operations",
)
async def test_openapi_declares_auth_for_privileged_routes(client):
    schema = (await client.get("/openapi.json")).json()
    for method in ("get", "post"):
        assert schema["paths"]["/api/v1/jobs"][method].get("security")


async def test_public_health_is_accessible(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.parametrize("target", ["http://127.0.0.1/qa", "http://10.0.0.1/qa", "http://[::1]/qa"])
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-011: static fetcher permits nonpublic destinations",
)
async def test_static_fetch_blocks_nonpublic_destinations(target):
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(200, text="<html><body>QA fixture</body></html>")

    job = ScrapeJob(name="QA fixture", start_url=target)
    fetcher = fetcher_static.StaticFetcher(job)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as session:
        fetcher.session = session
        await fetcher.fetch(target)
    assert requested == []


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="BE-011: redirect targets are not revalidated"
)
async def test_static_fetch_blocks_public_to_private_redirect(monkeypatch):
    requested = []
    original_client = httpx.AsyncClient

    def respond(request):
        requested.append(str(request.url))
        if request.url.host == "example.test":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/qa"})
        return httpx.Response(200, text="<html><body>QA fixture</body></html>")

    def isolated_client(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(fetcher_static.httpx, "AsyncClient", isolated_client)
    job = ScrapeJob(name="QA fixture", start_url="https://example.test")
    async with fetcher_static.StaticFetcher(job) as fetcher:
        await fetcher.fetch(job.start_url)
    assert requested == ["https://example.test"]


async def test_static_fetch_public_fixture_positive_control():
    job = ScrapeJob(name="QA fixture", start_url="https://example.test")
    fetcher = fetcher_static.StaticFetcher(job)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="<html><body>QA fixture</body></html>")
    )
    async with httpx.AsyncClient(transport=transport) as session:
        fetcher.session = session
        soup, html = await fetcher.fetch(job.start_url)
    assert soup.get_text() == "QA fixture"
    assert "QA fixture" in html


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-011: analyze API fetches private URLs anonymously",
)
async def test_analyze_rejects_nonpublic_url(client, monkeypatch):
    original_client = httpx.AsyncClient
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(
            200, text="<html><head><title>QA fixture</title></head><body>QA</body></html>"
        )

    def isolated_client(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(fetcher_static.httpx, "AsyncClient", isolated_client)
    response = await client.post("/api/v1/analyze", json={"url": "http://127.0.0.1/qa"})
    assert response.status_code in (400, 403, 422)
    assert requested == []


async def run_stubbed_export_job(client, monkeypatch, tmp_path, filename):
    """Exercise real API create/run/export while replacing only scraper I/O."""

    class FixtureEngine:
        async def _generate_urls(self, job):
            return [job.start_url]

    class FixtureConcurrentScraper:
        def __init__(self, job, max_workers):
            self.job = job

        async def add_urls(self, urls):
            pass

        async def run(self, scrape_single):
            return ScrapeResult(
                job_id=self.job.id,
                status="success",
                items_scraped=1,
                data=[{"title": "QA fixture"}],
                metadata={"job_name": self.job.name},
            )

    monkeypatch.setattr(engine_module, "ScraperEngine", FixtureEngine)
    monkeypatch.setattr(api, "ConcurrentScraper", FixtureConcurrentScraper)
    payload = {
        "id": "qa_export",
        "name": "QA fixture",
        "start_url": "https://example.test",
        "export": {
            "base_path": str(tmp_path / "exports"),
            "formats": ["json"],
            "filename_template": filename,
        },
    }
    created = await client.post("/api/v1/jobs", json={"job": payload})
    assert created.status_code == 200
    started = await client.post("/api/v1/jobs/qa_export/run?concurrent=true")
    assert started.status_code == 200
    task = api.running_jobs.get("qa_export")
    if task is not None:
        await task


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="BE-012: API export filename can escape base_path"
)
async def test_api_export_cannot_overwrite_sibling_marker(client, monkeypatch, tmp_path):
    marker = tmp_path / "outside.json"
    marker.write_text("original QA marker", encoding="utf-8")
    await run_stubbed_export_job(client, monkeypatch, tmp_path, "../outside")
    assert marker.read_text(encoding="utf-8") == "original QA marker"


async def test_api_export_with_safe_filename_positive_control(client, monkeypatch, tmp_path):
    await run_stubbed_export_job(client, monkeypatch, tmp_path, "inside")
    assert (tmp_path / "exports" / "inside.json").is_file()


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="BE-013: pagination has no server-side upper bound"
)
def test_pagination_rejects_excessive_work_budget():
    # Validate only: never expand this count into a URL list or run a scrape.
    rejected = False
    try:
        PaginationConfig(
            mode="url_pattern", url_pattern="https://example.test/{page}", max_pages=10**9
        )
    except ValidationError:
        rejected = True
    assert rejected


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-013: API accepts billion-page job without a work cap",
)
async def test_api_rejects_excessive_work_budget(client):
    response = await client.post(
        "/api/v1/jobs",
        json={
            "job": {
                "id": "qa_budget",
                "name": "QA budget fixture",
                "start_url": "https://example.test",
                "pagination": {
                    "mode": "url_pattern",
                    "url_pattern": "https://example.test/{page}",
                    "max_pages": 10**9,
                },
            }
        },
    )
    # Only create/validate configuration; never run this job or allocate its URLs.
    assert response.status_code == 422


def install_robots_fixture(monkeypatch):
    requested = []
    original_client = httpx.AsyncClient

    def respond(request):
        requested.append(request.url.path)
        body = (
            "User-agent: *\nDisallow: /\n"
            if request.url.path == "/robots.txt"
            else "<html>QA</html>"
        )
        return httpx.Response(200, text=body)

    def isolated_client(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(fetcher_static.httpx, "AsyncClient", isolated_client)
    job = ScrapeJob(
        id="qa_robots",
        name="QA robots fixture",
        start_url="https://example.test/qa",
        rate_limit={"min_delay": 0, "max_delay": 0, "respect_robots_txt": True},
    )
    return job, requested


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="BE-014: engine ignores respect_robots_txt"
)
async def test_engine_respects_robots_disallow(monkeypatch):
    job, requested = install_robots_fixture(monkeypatch)
    result = await engine_module.ScraperEngine().run_job(job)
    assert "/qa" not in requested
    assert result.pages_visited == 0


async def test_robots_parser_rejects_disallow_positive_control(monkeypatch):
    job, requested = install_robots_fixture(monkeypatch)
    async with fetcher_static.StaticFetcher(job) as fetcher:
        assert await fetcher.check_robots_txt(job.start_url) is False
    assert requested == ["/robots.txt"]


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-015: API rate-limit rejection logs raw identifier",
)
def test_api_rate_limiter_does_not_log_credential_identifier(caplog):
    # A non-secret fixture, never a generated key or a user credential.
    identifier = "qa-nonsecret-marker"
    allowed, _ = APIRateLimiter().check_rate_limit(identifier, limit=0)
    assert allowed is False
    assert identifier not in caplog.text

"""Real in-process routes; known defects retain desired assertions as strict xfails."""

import asyncio
import re

import pytest

from scraper.api import rest_server as api
from scraper.config.models import ScrapeResult


async def test_openapi_declares_create_contract(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["paths"]["/api/v1/jobs"]["post"]["requestBody"]
    assert schema["components"]["schemas"]["JobCreateRequest"]["required"] == ["job"]


async def test_create_read_list_delete_and_duplicate(client, job):
    payload = {"job": job.model_dump(mode="json")}
    assert (await client.post("/api/v1/jobs", json=payload)).status_code == 200
    assert (await client.post("/api/v1/jobs", json=payload)).status_code == 400
    response = await client.get(f"/api/v1/jobs/{job.id}")
    assert response.status_code == 200
    assert response.json()["id"] == job.id
    assert (await client.get("/api/v1/jobs")).json()["total"] == 1
    assert (await client.get(f"/api/v1/jobs/{job.id}/status")).json() == {
        "job_id": job.id, "is_running": False, "has_result": False,
    }
    assert (await client.delete(f"/api/v1/jobs/{job.id}")).status_code == 200
    assert (await client.get(f"/api/v1/jobs/{job.id}")).status_code == 404


@pytest.mark.parametrize("suffix", ["", "/status", "/results"])
async def test_missing_job_returns_404(client, suffix):
    assert (await client.get(f"/api/v1/jobs/absent{suffix}")).status_code == 404


@pytest.mark.parametrize("payload", [{}, {"job": {}}, {"job": {"name": "x", "start_url": "file:///tmp/fixture"}}])
async def test_create_rejects_invalid_input(client, payload):
    assert (await client.post("/api/v1/jobs", json=payload)).status_code == 422


async def test_concurrent_run_requests_start_only_once(client, job, monkeypatch):
    api.jobs_db[job.id] = job
    gate = asyncio.Event()
    starts = []

    async def blocked_execute(*args):
        starts.append(args[0])
        await gate.wait()

    monkeypatch.setattr(api, "_execute_job", blocked_execute)
    responses = await asyncio.gather(*[
        client.post(f"/api/v1/jobs/{job.id}/run") for _ in range(8)
    ])
    await asyncio.sleep(0)
    assert sorted(response.status_code for response in responses) == [200] + [400] * 7
    assert starts == [job.id]


async def test_delete_cancels_active_task(client, job, monkeypatch):
    api.jobs_db[job.id] = job
    gate = asyncio.Event()
    monkeypatch.setattr(api, "_execute_job", lambda *args: gate.wait())
    await client.post(f"/api/v1/jobs/{job.id}/run")
    task = api.running_jobs[job.id]
    assert (await client.delete(f"/api/v1/jobs/{job.id}")).status_code == 200
    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert job.id not in api.running_jobs


async def test_results_pagination_boundaries(client, job):
    api.results_db[job.id] = ScrapeResult(
        job_id=job.id, status="success", items_scraped=3, data=[{"n": n} for n in range(3)],
    )
    first = (await client.get(f"/api/v1/jobs/{job.id}/results?limit=2&offset=0")).json()
    last = (await client.get(f"/api/v1/jobs/{job.id}/results?limit=2&offset=2")).json()
    assert first["items"] == [{"n": 0}, {"n": 1}]
    assert first["pagination"]["has_more"] is True
    assert last["items"] == [{"n": 2}]
    assert last["pagination"]["has_more"] is False


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BE-004: server-generated IDs contain a dot rejected by detail/delete")
async def test_server_generated_job_id_round_trips(client, job):
    payload = job.model_dump(mode="json")
    del payload["id"]
    created = await client.post("/api/v1/jobs", json={"job": payload})
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    assert (await client.get(f"/api/v1/jobs/{job_id}")).status_code == 200
    assert (await client.delete(f"/api/v1/jobs/{job_id}")).status_code == 200


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BE-008: results accepts zero/negative limit and negative offset")
@pytest.mark.parametrize("query", ["limit=0", "limit=-1", "offset=-1"])
async def test_invalid_results_pagination_is_rejected(client, job, query):
    api.results_db[job.id] = ScrapeResult(
        job_id=job.id, status="success", items_scraped=3, data=[{"n": n} for n in range(3)],
    )
    assert (await client.get(f"/api/v1/jobs/{job.id}/results?{query}")).status_code == 422


async def test_workflow_without_dependencies_round_trips(client):
    created = await client.post("/api/v1/workflows", json={
        "name": "independent", "nodes": [{"id": "a", "type": "scrape"}],
    })
    assert created.status_code == 200
    assert (await client.get("/api/v1/workflows")).json()["total"] == 1
    assert (await client.get("/api/v1/workflows/independent")).status_code == 200


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="BE-005: invalid workflow nodes/DAG errors escape as 500")
@pytest.mark.parametrize("nodes", [
    [{}],
    [{"id": "a", "type": "scrape", "depends_on": ["missing"]}],
    [{"id": "a", "type": "scrape", "depends_on": ["a"]}],
])
async def test_bad_workflow_returns_validation_error(client, nodes):
    response = await client.post("/api/v1/workflows", json={"name": "invalid", "nodes": nodes})
    assert response.status_code in (400, 422)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="FE-001: root dashboard app.js path is not served")
async def test_dashboard_script_is_available(client):
    page = await client.get("/")
    assert page.status_code == 200
    scripts = re.findall(r'<script[^>]+src="([^\"]+)"', page.text)
    assert scripts
    local_scripts = [path for path in scripts if not path.startswith(("https://", "http://"))]
    assert local_scripts
    for path in local_scripts:
        response = await client.get("/" + path.lstrip("/"))
        assert response.status_code == 200


async def test_mounted_dashboard_script_is_available(client):
    assert (await client.get("/static/app.js")).status_code == 200


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="FE-002: dashboard max_pages is an ignored top-level field")
async def test_dashboard_requested_page_limit_is_preserved(client, job):
    payload = job.model_dump(mode="json")
    payload["pagination"] = {"mode": "none"}
    payload["max_pages"] = 2
    assert (await client.post("/api/v1/jobs", json={"job": payload})).status_code == 200
    assert api.jobs_db[job.id].pagination.max_pages == 2


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="FE-003: dashboard export.format is ignored; CSV default wins")
async def test_dashboard_requested_export_format_is_preserved(client, job):
    payload = job.model_dump(mode="json")
    payload["export"] = {"format": "json", "base_path": str(job.export.base_path)}
    assert (await client.post("/api/v1/jobs", json={"job": payload})).status_code == 200
    assert api.jobs_db[job.id].export.formats == ["json"]

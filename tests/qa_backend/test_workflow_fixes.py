"""BE-005 workflow ordering and invalid-definition regressions."""

import httpx
import pytest

from scraper.api import rest_server as api
from scraper.scheduler.workflow_dag import WorkflowDAG, WorkflowNode


def test_workflow_keeps_all_nodes_and_parallel_prerequisites() -> None:
    workflow = WorkflowDAG("branching")
    # Dependents may be declared first; shared prerequisites execute once.
    for node in [
        WorkflowNode(id="export", type="export", depends_on=["left", "right"]),
        WorkflowNode(id="right", type="transform", depends_on=["fetch"]),
        WorkflowNode(id="independent", type="scrape"),
        WorkflowNode(id="fetch", type="scrape"),
        WorkflowNode(id="left", type="transform", depends_on=["fetch"]),
    ]:
        workflow.add_node(node)
    workflow.build()
    assert workflow.execution_order == [
        ["independent", "fetch"], ["right", "left"], ["export"],
    ]


def test_workflow_repeated_prerequisite_executes_once() -> None:
    workflow = WorkflowDAG("repeated-edge")
    workflow.add_node(WorkflowNode(id="fetch", type="scrape"))
    workflow.add_node(WorkflowNode(id="export", type="export", depends_on=["fetch", "fetch"]))
    workflow.build()
    assert workflow.execution_order == [["fetch"], ["export"]]


@pytest.mark.parametrize("nodes, message", [
    ([WorkflowNode(id="a", type="scrape", depends_on=["missing"])], "missing"),
    ([WorkflowNode(id="a", type="scrape", depends_on=["a"])], "cycle"),
    ([
        WorkflowNode(id="a", type="scrape", depends_on=["b"]),
        WorkflowNode(id="b", type="transform", depends_on=["a"]),
    ], "cycle"),
])
def test_workflow_rejects_invalid_dependencies(nodes: list[WorkflowNode], message: str) -> None:
    workflow = WorkflowDAG("invalid")
    for node in nodes:
        workflow.add_node(node)
    with pytest.raises(ValueError, match=message):
        workflow.build()
    assert workflow.execution_order == []


def test_workflow_rejects_duplicate_node_ids() -> None:
    workflow = WorkflowDAG("duplicates")
    workflow.add_node(WorkflowNode(id="fetch", type="scrape"))
    with pytest.raises(ValueError, match="already exists"):
        workflow.add_node(WorkflowNode(id="fetch", type="export"))


async def test_workflow_executes_prerequisite_before_dependent() -> None:
    workflow = WorkflowDAG("execute-chain")
    workflow.add_node(WorkflowNode(id="export", type="fixture", depends_on=["fetch"]))
    workflow.add_node(WorkflowNode(id="fetch", type="fixture"))
    calls = []

    async def execute(node: WorkflowNode, context: dict[str, str]) -> str:
        if node.id == "export":
            assert context["result_fetch"] == "fetched"
        calls.append(node.id)
        return "fetched" if node.id == "fetch" else "exported"

    result = await workflow.execute({"fixture": execute})
    assert calls == ["fetch", "export"]
    assert result["status"] == "success"
    assert result["nodes"]["export"]["result"] == "exported"


@pytest.mark.parametrize("nodes", [
    [{"id": "a", "type": "scrape"}, {"id": "a", "type": "export"}],
    [
        {"id": "a", "type": "scrape", "depends_on": ["b"]},
        {"id": "b", "type": "export", "depends_on": ["a"]},
    ],
    [{"id": "a", "type": "scrape", "unknown_field": True}],
])
async def test_workflow_api_rejects_invalid_definition_without_persisting(
    client: httpx.AsyncClient, nodes: list[dict[str, object]],
) -> None:
    response = await client.post("/api/v1/workflows", json={"name": "invalid", "nodes": nodes})
    assert response.status_code in (400, 422)
    assert "invalid" not in api.workflows_db


async def test_workflow_api_persists_complete_dependency_plan(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/workflows", json={
        "name": "valid-chain", "nodes": [
            {"id": "export", "type": "export", "depends_on": ["fetch"]},
            {"id": "fetch", "type": "scrape"},
        ],
    })
    assert response.status_code == 200
    assert response.json()["execution_levels"] == 2
    assert api.workflows_db["valid-chain"].execution_order == [["fetch"], ["export"]]

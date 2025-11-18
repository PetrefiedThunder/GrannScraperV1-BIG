"""
Full-featured workflow DAG engine.

Create complex scraping workflows with:
- Dependencies between jobs
- Conditional execution
- Parallel execution
- Error handling
- Retries and rollbacks
"""

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Status of a workflow node."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class WorkflowNode:
    """
    A node in the workflow DAG.

    Can be:
    - Scrape job
    - Transform operation
    - Export task
    - Conditional check
    """
    id: str
    type: str  # scrape, transform, export, condition, python
    config: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # Python expression
    retry_count: int = 3
    timeout_seconds: int = 300

    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0


class WorkflowDAG:
    """
    Directed Acyclic Graph workflow engine.

    Executes complex multi-step workflows with:
    - Automatic dependency resolution
    - Parallel execution where possible
    - Error handling and retries
    - Conditional branching
    - State management
    """

    def __init__(self, name: str):
        self.name = name
        self.nodes: Dict[str, WorkflowNode] = {}
        self.execution_order: List[List[str]] = []  # List of parallel batches

    def add_node(self, node: WorkflowNode):
        """Add a node to the workflow."""
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists")

        self.nodes[node.id] = node

    def build(self):
        """
        Build execution plan.

        Determines optimal execution order with maximum parallelism.
        """
        # Validate DAG (no cycles)
        self._validate_dag()

        # Topological sort with level assignment
        self.execution_order = self._topological_sort_with_levels()

        logger.info(
            f"Workflow built: {len(self.nodes)} nodes in "
            f"{len(self.execution_order)} parallel batches"
        )

    def _validate_dag(self):
        """Validate that graph is acyclic."""
        visited = set()
        rec_stack = set()

        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            node = self.nodes.get(node_id)
            if not node:
                return False

            for dep_id in node.depends_on:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if has_cycle(node_id):
                    raise ValueError(f"Workflow contains cycle involving {node_id}")

    def _topological_sort_with_levels(self) -> List[List[str]]:
        """
        Topological sort that groups nodes into parallel execution levels.

        Returns list of lists, where each inner list can execute in parallel.
        """
        # Calculate in-degree
        in_degree = {node_id: 0 for node_id in self.nodes}
        for node in self.nodes.values():
            for dep in node.depends_on:
                in_degree[dep] += 1

        # Find nodes with no dependencies
        queue = deque([
            node_id for node_id, degree in in_degree.items()
            if degree == 0
        ])

        levels = []

        while queue:
            # All nodes in queue can execute in parallel
            current_level = list(queue)
            levels.append(current_level)

            # Process current level
            next_queue = []
            for node_id in current_level:
                queue.popleft()

                # Reduce in-degree for dependent nodes
                for other_id, other_node in self.nodes.items():
                    if node_id in other_node.depends_on:
                        in_degree[other_id] -= 1
                        if in_degree[other_id] == 0:
                            next_queue.append(other_id)

            queue.extend(next_queue)

        return levels

    async def execute(
        self,
        executor_map: Dict[str, Callable],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the workflow.

        Args:
            executor_map: Map of node type to executor function
            context: Shared context passed to all nodes

        Returns:
            Workflow execution results
        """
        if not self.execution_order:
            self.build()

        context = context or {}
        start_time = datetime.utcnow()

        logger.info(f"Starting workflow: {self.name}")

        # Execute each level
        for level_idx, level_nodes in enumerate(self.execution_order):
            logger.info(
                f"Executing level {level_idx + 1}/{len(self.execution_order)}: "
                f"{len(level_nodes)} nodes"
            )

            # Execute nodes in parallel
            tasks = []
            for node_id in level_nodes:
                task = self._execute_node(node_id, executor_map, context)
                tasks.append(task)

            # Wait for all nodes in level to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for failures
            failed = [
                node_id for node_id in level_nodes
                if self.nodes[node_id].status == NodeStatus.FAILED
            ]

            if failed:
                logger.error(f"Nodes failed: {failed}")
                # Handle failure based on error handling policy
                # For now, continue

        # Workflow complete
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Collect results
        workflow_result = {
            'name': self.name,
            'status': self._get_overall_status(),
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': duration,
            'nodes': {
                node_id: {
                    'status': node.status.value,
                    'result': node.result,
                    'error': node.error,
                    'attempts': node.attempts,
                }
                for node_id, node in self.nodes.items()
            }
        }

        logger.info(
            f"Workflow complete: {self.name} "
            f"(status: {workflow_result['status']}, duration: {duration:.2f}s)"
        )

        return workflow_result

    async def _execute_node(
        self,
        node_id: str,
        executor_map: Dict[str, Callable],
        context: Dict[str, Any]
    ):
        """Execute a single node."""
        node = self.nodes[node_id]

        # Check if dependencies succeeded
        for dep_id in node.depends_on:
            dep_node = self.nodes[dep_id]
            if dep_node.status != NodeStatus.SUCCESS:
                logger.warning(
                    f"Skipping {node_id} - dependency {dep_id} "
                    f"not successful (status: {dep_node.status})"
                )
                node.status = NodeStatus.SKIPPED
                return

        # Check condition if present
        if node.condition:
            if not self._evaluate_condition(node.condition, context):
                logger.info(f"Skipping {node_id} - condition not met")
                node.status = NodeStatus.SKIPPED
                return

        # Execute with retries
        node.status = NodeStatus.RUNNING
        node.start_time = datetime.utcnow()

        executor = executor_map.get(node.type)
        if not executor:
            logger.error(f"No executor for node type: {node.type}")
            node.status = NodeStatus.FAILED
            node.error = f"No executor for type: {node.type}"
            return

        # Retry loop
        for attempt in range(node.retry_count):
            node.attempts = attempt + 1

            try:
                logger.debug(
                    f"Executing {node_id} (attempt {attempt + 1}/{node.retry_count})"
                )

                # Execute with timeout
                result = await asyncio.wait_for(
                    executor(node, context),
                    timeout=node.timeout_seconds
                )

                # Success
                node.result = result
                node.status = NodeStatus.SUCCESS
                node.end_time = datetime.utcnow()

                # Update context with result
                context[f'result_{node_id}'] = result

                logger.info(f"Node {node_id} completed successfully")
                return

            except asyncio.TimeoutError:
                logger.warning(f"Node {node_id} timed out")
                node.error = f"Timeout after {node.timeout_seconds}s"

            except Exception as e:
                logger.warning(f"Node {node_id} failed: {e}")
                node.error = str(e)

            # Wait before retry (exponential backoff)
            if attempt < node.retry_count - 1:
                backoff = 2 ** attempt
                logger.debug(f"Waiting {backoff}s before retry...")
                await asyncio.sleep(backoff)

        # All retries failed
        node.status = NodeStatus.FAILED
        node.end_time = datetime.utcnow()
        logger.error(f"Node {node_id} failed after {node.retry_count} attempts")

    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """
        Evaluate a condition expression.

        Conditions are Python expressions with access to context.
        """
        try:
            # Safe evaluation with limited scope
            safe_context = {
                'context': context,
                'len': len,
                'sum': sum,
                'max': max,
                'min': min,
            }

            result = eval(condition, {"__builtins__": {}}, safe_context)
            return bool(result)

        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False

    def _get_overall_status(self) -> str:
        """Get overall workflow status."""
        statuses = [node.status for node in self.nodes.values()]

        if any(s == NodeStatus.FAILED for s in statuses):
            return "failed"
        elif any(s == NodeStatus.RUNNING for s in statuses):
            return "running"
        elif all(s == NodeStatus.SUCCESS for s in statuses):
            return "success"
        elif all(s in (NodeStatus.SUCCESS, NodeStatus.SKIPPED) for s in statuses):
            return "success_with_skips"
        else:
            return "partial"

    def get_execution_plan(self) -> str:
        """Get human-readable execution plan."""
        if not self.execution_order:
            self.build()

        plan = [f"Workflow: {self.name}\n"]
        plan.append(f"Total nodes: {len(self.nodes)}\n")
        plan.append(f"Execution levels: {len(self.execution_order)}\n\n")

        for level_idx, level_nodes in enumerate(self.execution_order):
            plan.append(f"Level {level_idx + 1} (parallel):\n")
            for node_id in level_nodes:
                node = self.nodes[node_id]
                deps = ", ".join(node.depends_on) if node.depends_on else "none"
                plan.append(f"  - {node_id} (type: {node.type}, depends: {deps})\n")
            plan.append("\n")

        return "".join(plan)


class WorkflowBuilder:
    """
    Fluent builder for creating workflows.

    Example:
        workflow = (WorkflowBuilder("my_workflow")
            .scrape("scrape_products", url="https://example.com")
            .transform("clean_data", depends_on=["scrape_products"])
            .export("save_csv", depends_on=["clean_data"])
            .build())
    """

    def __init__(self, name: str):
        self.workflow = WorkflowDAG(name)

    def scrape(
        self,
        node_id: str,
        job_id: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        **config
    ) -> "WorkflowBuilder":
        """Add a scrape node."""
        node = WorkflowNode(
            id=node_id,
            type="scrape",
            config={'job_id': job_id, **config},
            depends_on=depends_on or []
        )
        self.workflow.add_node(node)
        return self

    def transform(
        self,
        node_id: str,
        transform_type: str = "clean",
        depends_on: Optional[List[str]] = None,
        **config
    ) -> "WorkflowBuilder":
        """Add a transform node."""
        node = WorkflowNode(
            id=node_id,
            type="transform",
            config={'transform_type': transform_type, **config},
            depends_on=depends_on or []
        )
        self.workflow.add_node(node)
        return self

    def export(
        self,
        node_id: str,
        export_format: str = "csv",
        depends_on: Optional[List[str]] = None,
        **config
    ) -> "WorkflowBuilder":
        """Add an export node."""
        node = WorkflowNode(
            id=node_id,
            type="export",
            config={'format': export_format, **config},
            depends_on=depends_on or []
        )
        self.workflow.add_node(node)
        return self

    def condition(
        self,
        node_id: str,
        condition: str,
        depends_on: Optional[List[str]] = None
    ) -> "WorkflowBuilder":
        """Add a conditional node."""
        node = WorkflowNode(
            id=node_id,
            type="condition",
            condition=condition,
            depends_on=depends_on or []
        )
        self.workflow.add_node(node)
        return self

    def python(
        self,
        node_id: str,
        function: Callable,
        depends_on: Optional[List[str]] = None,
        **config
    ) -> "WorkflowBuilder":
        """Add a custom Python function node."""
        node = WorkflowNode(
            id=node_id,
            type="python",
            config={'function': function, **config},
            depends_on=depends_on or []
        )
        self.workflow.add_node(node)
        return self

    def build(self) -> WorkflowDAG:
        """Build and return the workflow."""
        self.workflow.build()
        return self.workflow

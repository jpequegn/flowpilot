"""Parallel node executor for FlowPilot."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import ParallelNode

logger = logging.getLogger(__name__)


@ExecutorRegistry.register("parallel")
class ParallelExecutor(NodeExecutor):
    """Execute nodes in parallel with configurable concurrency."""

    async def execute(
        self,
        node: ParallelNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Validate and prepare parallel execution.

        The parallel executor validates the node configuration and returns
        the execution plan. Actual parallel execution is handled by the runner.

        Args:
            node: The parallel node to execute.
            context: The execution context.

        Returns:
            NodeResult with parallel execution configuration.
        """
        started_at = datetime.now()

        try:
            # Validate node IDs are specified
            if not node.nodes:
                return NodeResult(
                    status="success",
                    output={"completed": 0, "results": {}},
                    data={
                        "parallel_nodes": [],
                        "max_concurrency": None,
                        "fail_fast": node.fail_fast,
                        "timeout": node.timeout,
                        "empty_parallel": True,
                    },
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            logger.debug(
                f"Parallel {node.id}: preparing to execute {len(node.nodes)} nodes "
                f"(max_concurrency={node.max_concurrency}, fail_fast={node.fail_fast})"
            )

            # Return parallel configuration for the runner to execute
            return NodeResult(
                status="success",
                output={
                    "parallel_nodes": node.nodes,
                    "max_concurrency": node.max_concurrency,
                },
                data={
                    "parallel_nodes": node.nodes,
                    "max_concurrency": node.max_concurrency,
                    "fail_fast": node.fail_fast,
                    "timeout": node.timeout,
                    "node_count": len(node.nodes),
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        except Exception as e:
            logger.exception(f"Parallel {node.id}: unexpected error")
            return NodeResult(
                status="error",
                error_message=f"Parallel execution error: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)

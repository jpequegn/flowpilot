"""Workflow runner for FlowPilot."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING, Any

from flowpilot.models import (
    ConditionNode,
    InputDefinition,
    LoopNode,
    Node,
    ParallelNode,
    RetryConfig,
    Workflow,
)

from .context import ExecutionContext, NodeResult
from .error_reporter import ErrorReport, get_error_reporter
from .executor import ExecutorRegistry, get_node_timeout
from .retry import RetryExecutor
from .template import TemplateEngine

if TYPE_CHECKING:
    from flowpilot.storage import Database

logger = logging.getLogger(__name__)


class WorkflowRunnerError(Exception):
    """Error during workflow execution."""


class CircularDependencyError(WorkflowRunnerError):
    """Circular dependency detected in workflow."""


class WorkflowRunner:
    """Executes workflows by running nodes in dependency order."""

    def __init__(
        self,
        db: Database | None = None,
        default_retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the workflow runner.

        Args:
            db: Optional database for persisting execution records.
            default_retry_config: Default retry configuration for nodes without explicit config.
        """
        self.template_engine = TemplateEngine()
        self._db = db
        self._retry_executor = RetryExecutor(default_retry_config)
        self._error_reporter = get_error_reporter()

    async def run(
        self,
        workflow: Workflow,
        inputs: dict[str, Any] | None = None,
        execution_id: str | None = None,
        workflow_path: str | None = None,
        trigger_type: str = "manual",
    ) -> ExecutionContext:
        """Execute a workflow and return context with all results.

        Args:
            workflow: The workflow to execute.
            inputs: Input values for the workflow.
            execution_id: Optional execution ID (generated if not provided).
            workflow_path: Path to the workflow file (for logging).
            trigger_type: How the workflow was triggered (manual, cron, webhook, etc.).

        Returns:
            ExecutionContext with all node results.

        Raises:
            CircularDependencyError: If workflow has circular dependencies.
            WorkflowRunnerError: If execution fails.
        """
        # Create execution context
        context = ExecutionContext(
            workflow_name=workflow.name,
            execution_id=execution_id or str(uuid.uuid4()),
            inputs=self._merge_inputs(workflow.inputs, inputs or {}),
            started_at=datetime.now(),
        )

        # Create execution record in database
        self._create_execution_record(context, workflow_path or "", trigger_type)

        # Create error report for this execution
        error_report = self._error_reporter.create_report(
            execution_id=context.execution_id,
            workflow_name=workflow.name,
            total_nodes=len(workflow.nodes),
        )

        try:
            # Build and validate dependency graph
            graph = self._build_dependency_graph(workflow)

            # Get execution order
            try:
                sorter = TopologicalSorter(graph)
                execution_order = list(sorter.static_order())
            except CycleError as e:
                raise CircularDependencyError(f"Circular dependency detected: {e}") from e

            # Execute nodes in order
            for node_id in execution_order:
                node = self._get_node(workflow, node_id)
                if node is None:
                    continue  # Skip nodes that don't exist (shouldn't happen)

                # Check if we should skip this node
                if self._should_skip_node(node, context):
                    context.set_node_result(node_id, NodeResult.skipped("Condition not met"))
                    continue

                # Handle loop nodes specially
                if isinstance(node, LoopNode):
                    result = await self._execute_loop_node(node, context, workflow, error_report)
                elif isinstance(node, ParallelNode):
                    result = await self._execute_parallel_node(
                        node, context, workflow, error_report
                    )
                else:
                    # Execute the node with retry and fallback support
                    result = await self._execute_node(node, context, workflow, error_report)

                context.set_node_result(node_id, result)

                # Check if we should stop on error
                # Stop if: error AND on_error=stop AND NOT continue_on_error
                should_stop = (
                    result.status == "error"
                    and workflow.settings.on_error == "stop"
                    and not node.continue_on_error
                    and not result.data.get("continued_on_error", False)
                )

                if should_stop:
                    context.mark_finished("error")
                    error_report.finish()
                    self._finalize_execution_record(context, workflow)
                    return context

            # Mark successful completion
            context.mark_finished("error" if context.has_errors else "success")
            error_report.finish()

        except CircularDependencyError:
            context.mark_finished("error")
            self._finalize_execution_record(context, workflow, error="Circular dependency")
            raise
        except Exception as e:
            context.mark_finished("error")
            self._finalize_execution_record(context, workflow, error=str(e))
            raise WorkflowRunnerError(f"Workflow execution failed: {e}") from e

        # Save final execution state
        self._finalize_execution_record(context, workflow)

        return context

    def _create_execution_record(
        self,
        context: ExecutionContext,
        workflow_path: str,
        trigger_type: str,
    ) -> Any:
        """Create initial execution record in database.

        Args:
            context: The execution context.
            workflow_path: Path to the workflow file.
            trigger_type: How the workflow was triggered.

        Returns:
            The created Execution record, or None if no database.
        """
        if self._db is None:
            return None

        from flowpilot.storage import Execution, ExecutionRepository, ExecutionStatus

        with self._db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = Execution(
                id=context.execution_id,
                workflow_name=context.workflow_name,
                workflow_path=workflow_path,
                status=ExecutionStatus.RUNNING,
                trigger_type=trigger_type,
                inputs=context.inputs,
                started_at=context.started_at,
            )
            repo.create(execution)
            return execution

    def _finalize_execution_record(
        self,
        context: ExecutionContext,
        workflow: Workflow,
        error: str | None = None,
    ) -> None:
        """Update execution record with final state and save node results.

        Args:
            context: The execution context with results.
            workflow: The workflow definition.
            error: Optional error message if execution failed.
        """
        if self._db is None:
            return

        from flowpilot.storage import (
            ExecutionRepository,
            ExecutionStatus,
            NodeExecution,
            NodeExecutionRepository,
        )

        with self._db.session_scope() as session:
            # Update execution record
            repo = ExecutionRepository(session)
            execution = repo.get_by_id(context.execution_id)
            if execution is None:
                return

            # Map context status to ExecutionStatus
            status_map = {
                "success": ExecutionStatus.SUCCESS,
                "error": ExecutionStatus.FAILED,
                "cancelled": ExecutionStatus.CANCELLED,
                "running": ExecutionStatus.RUNNING,
            }
            execution.status = status_map.get(context.status, ExecutionStatus.FAILED)
            execution.finished_at = context.finished_at or datetime.now(UTC)
            execution.duration_ms = context.duration_ms
            execution.error = error

            repo.update(execution)

            # Create node execution records
            node_repo = NodeExecutionRepository(session)
            node_executions: list[NodeExecution] = []

            for node_id, result in context.nodes.items():
                # Get node type from workflow
                node = workflow.get_node(node_id)
                node_type = node.type if node else "unknown"

                # Serialize output to JSON string
                output_str = ""
                if result.output is not None:
                    try:
                        output_str = json.dumps(result.output)
                    except (TypeError, ValueError):
                        output_str = str(result.output)

                node_exec = NodeExecution(
                    execution_id=context.execution_id,
                    node_id=node_id,
                    node_type=node_type,
                    status=result.status,
                    started_at=result.started_at,
                    finished_at=result.finished_at,
                    duration_ms=result.duration_ms,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    output=output_str,
                    error=result.error_message,
                )
                node_executions.append(node_exec)

            if node_executions:
                node_repo.create_batch(node_executions)

    def _merge_inputs(
        self,
        definitions: dict[str, InputDefinition],
        provided: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge provided inputs with defaults.

        Args:
            definitions: Input definitions from workflow.
            provided: User-provided input values.

        Returns:
            Complete input dictionary with defaults applied.

        Raises:
            ValueError: If required input is missing.
        """
        result: dict[str, Any] = {}

        for name, definition in definitions.items():
            if name in provided:
                result[name] = provided[name]
            elif definition.default is not None:
                result[name] = definition.default
            elif definition.required:
                raise ValueError(f"Required input '{name}' not provided")

        # Include any extra inputs not defined in workflow
        for name, value in provided.items():
            if name not in result:
                result[name] = value

        return result

    def _build_dependency_graph(self, workflow: Workflow) -> dict[str, set[str]]:
        """Build dependency graph from workflow nodes.

        Args:
            workflow: The workflow to analyze.

        Returns:
            Dictionary mapping node IDs to their dependencies.
        """
        graph: dict[str, set[str]] = {}

        for node in workflow.nodes:
            deps: set[str] = set(node.depends_on)

            # Add control flow dependencies
            if isinstance(node, ConditionNode):
                # Condition node doesn't depend on its branches
                pass
            elif isinstance(node, LoopNode):
                # Loop node doesn't depend on its body
                pass
            elif isinstance(node, ParallelNode):
                # Parallel node doesn't depend on its parallel nodes
                pass

            graph[node.id] = deps

        return graph

    def _get_node(self, workflow: Workflow, node_id: str) -> Node | None:
        """Get a node from workflow by ID.

        Args:
            workflow: The workflow to search.
            node_id: The node ID to find.

        Returns:
            Node if found, None otherwise.
        """
        return workflow.get_node(node_id)

    def _should_skip_node(self, node: Node, context: ExecutionContext) -> bool:
        """Check if a node should be skipped based on dependencies.

        Args:
            node: The node to check.
            context: Current execution context.

        Returns:
            True if node should be skipped.
        """
        # Check if any dependency failed (and on_error is stop)
        for dep_id in node.depends_on:
            dep_result = context.get_node_result(dep_id)
            if dep_result and dep_result.status == "error":
                return True
            if dep_result and dep_result.status == "skipped":
                return True

        return False

    async def _execute_node(
        self,
        node: Node,
        context: ExecutionContext,
        workflow: Workflow,
        error_report: ErrorReport | None = None,
    ) -> NodeResult:
        """Execute a single node with retry and fallback support.

        Args:
            node: The node to execute.
            context: Current execution context.
            workflow: The parent workflow.
            error_report: Optional error report to record errors.

        Returns:
            NodeResult with execution outcome.
        """
        # Mark node as running
        started_at = datetime.now()

        # Check if executor is registered
        if not ExecutorRegistry.has_executor(node.type):
            return NodeResult.error(
                f"No executor registered for node type: {node.type}",
                started_at=started_at,
            )

        try:
            # Get executor and render node with templates
            executor = ExecutorRegistry.get(node.type)

            # Render template values in the node
            rendered_data = self.template_engine.render_dict(
                node.model_dump(),
                context.get_template_context(),
            )

            # Recreate node with rendered values
            rendered_node = type(node).model_validate(rendered_data)

            # Execute with retry logic if configured
            if node.retry is not None:
                result = await self._retry_executor.execute_with_retry(
                    executor, rendered_node, context
                )
            else:
                # Execute with timeout only
                timeout = get_node_timeout(node)
                result = await executor.execute_with_timeout(rendered_node, context, timeout)

            # Handle failure with fallback
            if result.status == "error" and node.fallback:
                fallback_result = await self._execute_fallback(
                    node, context, workflow, result, error_report
                )
                if fallback_result is not None:
                    return fallback_result

            # Handle continue_on_error
            if result.status == "error":
                # Record error in report
                if error_report:
                    error_report.add_error(
                        node_id=node.id,
                        error=result.error_message or "Unknown error",
                        category=result.data.get("final_error_category", "unknown"),
                        attempts=result.data.get("total_attempts", 1),
                        fallback_used=result.data.get("fallback_used", False),
                        continued=node.continue_on_error,
                    )

                if node.continue_on_error:
                    result.data["continued_on_error"] = True
                    logger.info(f"Node {node.id} failed but continue_on_error=True, continuing")

            return result

        except Exception as e:
            error_result = NodeResult.error(str(e), started_at=started_at)
            if error_report:
                error_report.add_error(
                    node_id=node.id,
                    error=str(e),
                    category="unknown",
                    attempts=1,
                    continued=node.continue_on_error,
                )
            return error_result

    async def _execute_fallback(
        self,
        node: Node,
        context: ExecutionContext,
        workflow: Workflow,
        original_result: NodeResult,
        error_report: ErrorReport | None = None,
    ) -> NodeResult | None:
        """Execute fallback node if available.

        Args:
            node: The original failed node.
            context: Current execution context.
            workflow: The parent workflow.
            original_result: Result from the failed node.
            error_report: Optional error report.

        Returns:
            Fallback result if successful, None if fallback fails or not available.
        """
        if node.fallback is None:
            return None
        fallback_node = self._get_node(workflow, node.fallback)
        if fallback_node is None:
            logger.warning(f"Fallback node '{node.fallback}' not found for node '{node.id}'")
            return None

        logger.info(f"Executing fallback node '{node.fallback}' for failed node '{node.id}'")

        # Execute fallback (without recursive fallback to prevent chains)
        fallback_node_copy = fallback_node.model_copy(update={"fallback": None})
        fallback_result = await self._execute_node(
            fallback_node_copy, context, workflow, error_report
        )

        if fallback_result.status == "success":
            # Merge information into result
            fallback_result.data["fallback_from"] = node.id
            fallback_result.data["fallback_used"] = True
            fallback_result.data["original_error"] = original_result.error_message

            # Record in error report
            if error_report:
                error_report.add_error(
                    node_id=node.id,
                    error=original_result.error_message or "Unknown error",
                    category=original_result.data.get("final_error_category", "unknown"),
                    attempts=original_result.data.get("total_attempts", 1),
                    fallback_used=True,
                )

            return fallback_result

        # Fallback also failed
        logger.warning(f"Fallback node '{node.fallback}' also failed")
        return None

    async def _execute_loop_node(
        self,
        node: LoopNode,
        context: ExecutionContext,
        workflow: Workflow,
        error_report: ErrorReport | None = None,
    ) -> NodeResult:
        """Execute a loop node, running child nodes for each iteration.

        Args:
            node: The loop node to execute.
            context: Current execution context.
            workflow: The parent workflow.
            error_report: Optional error report to record errors.

        Returns:
            NodeResult with loop execution results.
        """
        started_at = datetime.now()

        try:
            # First, execute the loop node itself to resolve for_each expression
            loop_result = await self._execute_node(node, context, workflow, error_report)

            if loop_result.status == "error":
                return loop_result

            # Get loop configuration from result
            loop_items = loop_result.data.get("loop_items", [])
            as_var = loop_result.data.get("as_var", "item")
            index_var = loop_result.data.get("index_var", "index")
            child_node_ids = loop_result.data.get("child_nodes", [])
            break_if = loop_result.data.get("break_if")

            # Handle empty loop
            if not loop_items:
                return NodeResult(
                    status="success",
                    output={"iterations": 0, "items_processed": []},
                    data={
                        "iterations": 0,
                        "total_items": 0,
                        "items_processed": [],
                        "break_triggered": False,
                    },
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            # Execute iterations
            items_processed: list[dict[str, Any]] = []
            break_triggered = False

            for index, item in enumerate(loop_items):
                # Set loop variables in context
                context.set_loop_variable(as_var, item)
                context.set_loop_variable(index_var, index)

                logger.debug(f"Loop {node.id}: iteration {index}, {as_var}={item}")

                # Check break condition before executing children
                if break_if and self._evaluate_break_condition(break_if, context):
                    logger.debug(f"Loop {node.id}: break condition met at iteration {index}")
                    break_triggered = True
                    break

                # Execute child nodes for this iteration
                iteration_results: list[NodeResult] = []
                iteration_failed = False

                for child_id in child_node_ids:
                    child_node = self._get_node(workflow, child_id)
                    if child_node is None:
                        logger.warning(f"Loop {node.id}: child node '{child_id}' not found")
                        continue

                    # Execute child node
                    child_result = await self._execute_node(
                        child_node, context, workflow, error_report
                    )

                    # Store result with iteration suffix
                    iteration_node_id = f"{child_id}[{index}]"
                    context.set_node_result(iteration_node_id, child_result)
                    iteration_results.append(child_result)

                    # Check if child failed
                    if child_result.status == "error" and not child_node.continue_on_error:
                        iteration_failed = True
                        break

                # Record iteration result
                items_processed.append(
                    {
                        "index": index,
                        "item": item,
                        "success": not iteration_failed,
                        "child_results": len(iteration_results),
                    }
                )

                # Stop loop on iteration failure (fail-fast behavior)
                if iteration_failed:
                    context.clear_loop_variables(as_var, index_var)
                    return NodeResult(
                        status="error",
                        error_message=f"Loop iteration {index} failed",
                        output={"iterations": index + 1, "items_processed": items_processed},
                        data={
                            "iterations": index + 1,
                            "total_items": len(loop_items),
                            "items_processed": items_processed,
                            "break_triggered": False,
                            "failed_at_iteration": index,
                        },
                        duration_ms=self._duration_ms(started_at),
                        started_at=started_at,
                        finished_at=datetime.now(),
                    )

            # Clear loop variables after completion
            context.clear_loop_variables(as_var, index_var)

            return NodeResult(
                status="success",
                output={
                    "iterations": len(items_processed),
                    "items_processed": items_processed,
                },
                data={
                    "iterations": len(items_processed),
                    "total_items": len(loop_items),
                    "items_processed": items_processed,
                    "break_triggered": break_triggered,
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        except Exception as e:
            logger.exception(f"Loop {node.id}: unexpected error")
            return NodeResult.error(f"Loop error: {e}", started_at=started_at)

    async def _execute_parallel_node(
        self,
        node: ParallelNode,
        context: ExecutionContext,
        workflow: Workflow,
        error_report: ErrorReport | None = None,
    ) -> NodeResult:
        """Execute a parallel node, running child nodes concurrently.

        Args:
            node: The parallel node to execute.
            context: Current execution context.
            workflow: The parent workflow.
            error_report: Optional error report to record errors.

        Returns:
            NodeResult with parallel execution results.
        """
        started_at = datetime.now()

        try:
            # First, execute the parallel node itself to get configuration
            parallel_result = await self._execute_node(node, context, workflow, error_report)

            if parallel_result.status == "error":
                return parallel_result

            # Get parallel configuration from result
            parallel_node_ids = parallel_result.data.get("parallel_nodes", [])
            max_concurrency = parallel_result.data.get("max_concurrency")
            fail_fast = parallel_result.data.get("fail_fast", True)
            timeout_seconds = parallel_result.data.get("timeout")

            # Handle empty parallel
            if not parallel_node_ids:
                return NodeResult(
                    status="success",
                    output={"completed": 0, "results": {}},
                    data={
                        "completed": 0,
                        "total_nodes": 0,
                        "results": {},
                        "errors": [],
                    },
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            # Create semaphore for concurrency limiting
            concurrency_limit = max_concurrency or len(parallel_node_ids)
            semaphore = asyncio.Semaphore(concurrency_limit)

            # Results storage
            results: dict[str, NodeResult] = {}
            errors: list[str] = []
            cancelled = False

            async def execute_with_semaphore(node_id: str) -> tuple[str, NodeResult]:
                """Execute a node with semaphore for concurrency control."""
                nonlocal cancelled
                async with semaphore:
                    if cancelled and fail_fast:
                        return node_id, NodeResult.skipped("Cancelled due to fail-fast")

                    child_node = self._get_node(workflow, node_id)
                    if child_node is None:
                        logger.warning(f"Parallel {node.id}: child node '{node_id}' not found")
                        return node_id, NodeResult.error(f"Node '{node_id}' not found")

                    result = await self._execute_node(child_node, context, workflow, error_report)
                    return node_id, result

            logger.debug(
                f"Parallel {node.id}: executing {len(parallel_node_ids)} nodes "
                f"(concurrency={concurrency_limit}, fail_fast={fail_fast})"
            )

            if fail_fast:
                # Fail-fast mode: cancel remaining on first error
                tasks = [
                    asyncio.create_task(execute_with_semaphore(node_id))
                    for node_id in parallel_node_ids
                ]

                try:
                    if timeout_seconds:
                        done, pending = await asyncio.wait(
                            tasks,
                            timeout=timeout_seconds,
                            return_when=asyncio.FIRST_EXCEPTION,
                        )
                    else:
                        done, pending = await asyncio.wait(
                            tasks,
                            return_when=asyncio.FIRST_EXCEPTION,
                        )

                    # Process completed tasks
                    for task in done:
                        try:
                            node_id, result = task.result()
                            results[node_id] = result
                            context.set_node_result(node_id, result)

                            if result.status == "error":
                                errors.append(node_id)
                                cancelled = True
                        except Exception as e:
                            logger.error(f"Task error: {e}")

                    # If we have errors and pending tasks, cancel them
                    if errors and pending:
                        for task in pending:
                            task.cancel()
                        # Wait for cancellation
                        await asyncio.gather(*pending, return_exceptions=True)

                    # If timeout occurred with pending tasks
                    if pending and not errors:
                        for task in pending:
                            task.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        return NodeResult(
                            status="error",
                            error_message=f"Parallel execution timed out after {timeout_seconds}s",
                            data={
                                "completed": len(results),
                                "total_nodes": len(parallel_node_ids),
                                "results": {k: v.status for k, v in results.items()},
                                "errors": errors,
                                "timed_out": True,
                            },
                            duration_ms=self._duration_ms(started_at),
                            started_at=started_at,
                            finished_at=datetime.now(),
                        )

                except TimeoutError:
                    # Cancel all pending tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    return NodeResult(
                        status="error",
                        error_message=f"Parallel execution timed out after {timeout_seconds}s",
                        data={
                            "completed": len(results),
                            "total_nodes": len(parallel_node_ids),
                            "results": {k: v.status for k, v in results.items()},
                            "errors": errors,
                            "timed_out": True,
                        },
                        duration_ms=self._duration_ms(started_at),
                        started_at=started_at,
                        finished_at=datetime.now(),
                    )

                # If fail-fast and we have errors, return error
                if errors:
                    return NodeResult(
                        status="error",
                        error_message=f"Parallel nodes failed: {', '.join(errors)}",
                        data={
                            "completed": len(results),
                            "total_nodes": len(parallel_node_ids),
                            "results": {k: v.status for k, v in results.items()},
                            "errors": errors,
                        },
                        duration_ms=self._duration_ms(started_at),
                        started_at=started_at,
                        finished_at=datetime.now(),
                    )

            else:
                # Wait-all mode: collect all results regardless of errors
                coroutines = [execute_with_semaphore(node_id) for node_id in parallel_node_ids]

                try:
                    if timeout_seconds:
                        completed = await asyncio.wait_for(
                            asyncio.gather(*coroutines, return_exceptions=True),
                            timeout=timeout_seconds,
                        )
                    else:
                        completed = await asyncio.gather(*coroutines, return_exceptions=True)

                    # Process results
                    for item in completed:
                        if isinstance(item, BaseException):
                            logger.error(f"Parallel task exception: {item}")
                            continue
                        node_id, result = item
                        results[node_id] = result
                        context.set_node_result(node_id, result)
                        if result.status == "error":
                            errors.append(node_id)

                except TimeoutError:
                    return NodeResult(
                        status="error",
                        error_message=f"Parallel execution timed out after {timeout_seconds}s",
                        data={
                            "completed": len(results),
                            "total_nodes": len(parallel_node_ids),
                            "results": {k: v.status for k, v in results.items()},
                            "errors": errors,
                            "timed_out": True,
                        },
                        duration_ms=self._duration_ms(started_at),
                        started_at=started_at,
                        finished_at=datetime.now(),
                    )

                # In wait-all mode, return error if any node failed
                if errors:
                    return NodeResult(
                        status="error",
                        error_message=f"Parallel nodes failed: {', '.join(errors)}",
                        data={
                            "completed": len(results),
                            "total_nodes": len(parallel_node_ids),
                            "results": {k: v.status for k, v in results.items()},
                            "errors": errors,
                        },
                        duration_ms=self._duration_ms(started_at),
                        started_at=started_at,
                        finished_at=datetime.now(),
                    )

            # All successful
            return NodeResult(
                status="success",
                output={
                    "completed": len(results),
                    "nodes": list(results.keys()),
                },
                data={
                    "completed": len(results),
                    "total_nodes": len(parallel_node_ids),
                    "results": {k: v.status for k, v in results.items()},
                    "errors": [],
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        except Exception as e:
            logger.exception(f"Parallel {node.id}: unexpected error")
            return NodeResult.error(f"Parallel error: {e}", started_at=started_at)

    def _evaluate_break_condition(self, expr: str, context: ExecutionContext) -> bool:
        """Evaluate a break condition expression.

        Args:
            expr: Break condition expression.
            context: Execution context with loop variables.

        Returns:
            True if loop should break.
        """
        from flowpilot.engine.nodes.loop import LoopExecutor

        executor = LoopExecutor()
        return executor._evaluate_break_condition(expr, context.get_template_context())

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)

    def validate_workflow(self, workflow: Workflow) -> list[str]:
        """Validate workflow before execution.

        Args:
            workflow: The workflow to validate.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []

        # Check for circular dependencies
        graph = self._build_dependency_graph(workflow)
        try:
            sorter = TopologicalSorter(graph)
            list(sorter.static_order())
        except CycleError as e:
            errors.append(f"Circular dependency detected: {e}")

        # Check all required node executors are registered
        for node in workflow.nodes:
            if not ExecutorRegistry.has_executor(node.type):
                errors.append(f"No executor registered for node type: {node.type}")

        return errors

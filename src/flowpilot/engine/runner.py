"""Workflow runner for FlowPilot."""

from __future__ import annotations

import json
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
    Workflow,
)

from .context import ExecutionContext, NodeResult
from .executor import ExecutorRegistry, get_node_timeout
from .template import TemplateEngine

if TYPE_CHECKING:
    from flowpilot.storage import Database


class WorkflowRunnerError(Exception):
    """Error during workflow execution."""


class CircularDependencyError(WorkflowRunnerError):
    """Circular dependency detected in workflow."""


class WorkflowRunner:
    """Executes workflows by running nodes in dependency order."""

    def __init__(self, db: Database | None = None) -> None:
        """Initialize the workflow runner.

        Args:
            db: Optional database for persisting execution records.
        """
        self.template_engine = TemplateEngine()
        self._db = db

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

                # Execute the node
                result = await self._execute_node(node, context, workflow)
                context.set_node_result(node_id, result)

                # Check if we should stop on error
                if result.status == "error" and workflow.settings.on_error == "stop":
                    context.mark_finished("error")
                    self._finalize_execution_record(context, workflow)
                    return context

            # Mark successful completion
            context.mark_finished("error" if context.has_errors else "success")

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
    ) -> NodeResult:
        """Execute a single node.

        Args:
            node: The node to execute.
            context: Current execution context.
            workflow: The parent workflow.

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
            # Note: This is a simplified approach - in production you might
            # want to handle this more carefully to preserve type information
            rendered_node = type(node).model_validate(rendered_data)

            # Execute with timeout
            timeout = get_node_timeout(node)
            result = await executor.execute_with_timeout(rendered_node, context, timeout)

            return result

        except Exception as e:
            return NodeResult.error(str(e), started_at=started_at)

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

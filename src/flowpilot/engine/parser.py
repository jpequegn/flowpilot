"""Workflow YAML parser for FlowPilot."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import ValidationError

from flowpilot.models import ConditionNode, LoopNode, ParallelNode, Workflow

if TYPE_CHECKING:
    from flowpilot.models import Node


class WorkflowParseError(Exception):
    """Error parsing workflow YAML."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class WorkflowParser:
    """Parser for workflow YAML files."""

    def parse_file(self, path: Path | str) -> Workflow:
        """Parse workflow from YAML file.

        Args:
            path: Path to the workflow YAML file.

        Returns:
            Parsed Workflow object.

        Raises:
            WorkflowParseError: If the file cannot be parsed.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        with open(path) as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise WorkflowParseError(f"Invalid YAML syntax: {e}") from e

        if data is None:
            raise WorkflowParseError("Empty workflow file")

        return self.parse_dict(data, source=str(path))

    def parse_string(self, content: str) -> Workflow:
        """Parse workflow from YAML string.

        Args:
            content: YAML content as string.

        Returns:
            Parsed Workflow object.

        Raises:
            WorkflowParseError: If the content cannot be parsed.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"Invalid YAML syntax: {e}") from e

        if data is None:
            raise WorkflowParseError("Empty workflow content")

        return self.parse_dict(data)

    def parse_dict(self, data: dict[str, Any], source: str = "<dict>") -> Workflow:
        """Parse workflow from dictionary.

        Args:
            data: Workflow data as dictionary.
            source: Source identifier for error messages.

        Returns:
            Parsed Workflow object.

        Raises:
            WorkflowParseError: If the data is invalid.
        """
        try:
            return Workflow.model_validate(data)
        except ValidationError as e:
            # Convert Pydantic errors to more readable format
            errors = []
            for error in e.errors():
                loc = " -> ".join(str(part) for part in error["loc"])
                errors.append(
                    {
                        "location": loc,
                        "message": error["msg"],
                        "type": error["type"],
                    }
                )

            error_messages = [f"  {err['location']}: {err['message']}" for err in errors]
            msg = f"Workflow validation failed ({source}):\n" + "\n".join(error_messages)
            raise WorkflowParseError(msg, errors=errors) from e

    def validate(self, workflow: Workflow) -> list[str]:
        """Return list of validation warnings.

        This performs additional checks beyond schema validation:
        - Unused nodes (nodes not referenced by any other node)
        - Potential circular dependencies
        - Unreachable nodes

        Args:
            workflow: Workflow to validate.

        Returns:
            List of warning messages.
        """
        warnings: list[str] = []
        node_ids = workflow.get_node_ids()

        # Find referenced nodes
        referenced: set[str] = set()
        for node in workflow.nodes:
            # Check depends_on
            referenced.update(node.depends_on)

            # Check condition references
            if isinstance(node, ConditionNode):
                referenced.add(node.then)
                if node.else_node:
                    referenced.add(node.else_node)

            # Check loop references
            if isinstance(node, LoopNode):
                referenced.add(node.do)

            # Check parallel references
            if isinstance(node, ParallelNode):
                referenced.update(node.nodes)

        # Find unreferenced nodes (except the first node which is the entry point)
        first_node_id = workflow.nodes[0].id if workflow.nodes else None
        unreferenced = node_ids - referenced - {first_node_id}
        if unreferenced:
            warnings.append(
                f"Potentially unreachable nodes (not referenced): {sorted(unreferenced)}"
            )

        # Check for self-references
        for node in workflow.nodes:
            if node.id in node.depends_on:
                warnings.append(f"Node '{node.id}' depends on itself")

        # Check for potential circular dependencies (simple check)
        warnings.extend(self._check_circular_dependencies(workflow))

        return warnings

    def _check_circular_dependencies(self, workflow: Workflow) -> list[str]:
        """Check for circular dependencies in the workflow.

        Returns:
            List of warning messages about circular dependencies.
        """
        warnings: list[str] = []

        # Build dependency graph
        graph: dict[str, set[str]] = {}
        for node in workflow.nodes:
            deps: set[str] = set(node.depends_on)

            # Add implicit dependencies from control flow
            if isinstance(node, ConditionNode):
                # Condition node doesn't depend on its branches
                pass
            if isinstance(node, LoopNode):
                # Loop node doesn't depend on its body
                pass
            if isinstance(node, ParallelNode):
                # Parallel node doesn't depend on its parallel nodes
                pass

            graph[node.id] = deps

        # DFS to detect cycles
        def has_cycle(node_id: str, visited: set[str], path: set[str]) -> str | None:
            if node_id in path:
                return node_id
            if node_id in visited:
                return None

            visited.add(node_id)
            path.add(node_id)

            for dep in graph.get(node_id, set()):
                cycle_node = has_cycle(dep, visited, path)
                if cycle_node:
                    return cycle_node

            path.remove(node_id)
            return None

        visited: set[str] = set()
        for node_id in graph:
            cycle_start = has_cycle(node_id, visited, set())
            if cycle_start:
                warnings.append(
                    f"Potential circular dependency detected involving node '{cycle_start}'"
                )
                break  # Only report one cycle

        return warnings

    def to_json_schema(self) -> dict[str, Any]:
        """Export JSON Schema for workflow validation.

        Returns:
            JSON Schema as dictionary.
        """
        return Workflow.model_json_schema()


def get_node_by_id(workflow: Workflow, node_id: str) -> Node | None:
    """Get a node from workflow by ID.

    Args:
        workflow: Workflow to search.
        node_id: Node ID to find.

    Returns:
        Node if found, None otherwise.
    """
    return workflow.get_node(node_id)

"""Workflow model for FlowPilot."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .nodes import ConditionNode, LoopNode, Node, ParallelNode
from .triggers import ManualTrigger, Trigger


class InputDefinition(BaseModel):
    """Definition for a workflow input parameter."""

    type: Literal["string", "number", "boolean", "array", "object"] = Field(
        default="string", description="Input type"
    )
    default: Any = Field(default=None, description="Default value")
    required: bool = Field(default=False, description="Whether input is required")
    description: str | None = Field(default=None, description="Input description")


class WorkflowSettings(BaseModel):
    """Workflow execution settings."""

    timeout: int = Field(default=300, ge=1, description="Total workflow timeout in seconds")
    retry: int = Field(default=0, ge=0, description="Number of retries on failure")
    retry_delay: int = Field(default=5, ge=0, description="Delay between retries in seconds")
    on_error: Literal["stop", "continue", "notify"] = Field(
        default="stop", description="Behavior on error"
    )


class Workflow(BaseModel):
    """Complete workflow definition."""

    name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Workflow name (lowercase, alphanumeric, hyphens)",
    )
    description: str = Field(default="", description="Workflow description")
    version: int = Field(default=1, ge=1, description="Workflow version")
    triggers: list[Trigger] = Field(
        default_factory=lambda: [ManualTrigger(type="manual")],  # type: ignore[arg-type]
        description="Workflow triggers",
    )
    inputs: dict[str, InputDefinition] = Field(default_factory=dict, description="Input parameters")
    nodes: list[Node] = Field(..., min_length=1, description="Workflow nodes")
    settings: WorkflowSettings = Field(
        default_factory=WorkflowSettings, description="Workflow settings"
    )

    @model_validator(mode="after")
    def validate_node_references(self) -> Workflow:
        """Validate all node ID references exist."""
        node_ids = {n.id for n in self.nodes}
        errors: list[str] = []

        for node in self.nodes:
            # Check depends_on references
            for dep_id in node.depends_on:
                if dep_id not in node_ids:
                    errors.append(f"Node '{node.id}' depends on unknown node '{dep_id}'")

            # Check condition node references
            if isinstance(node, ConditionNode):
                if node.then not in node_ids:
                    errors.append(
                        f"Condition node '{node.id}' references unknown 'then' node '{node.then}'"
                    )
                if node.else_node and node.else_node not in node_ids:
                    errors.append(
                        f"Condition node '{node.id}' references unknown 'else' node "
                        f"'{node.else_node}'"
                    )

            # Check loop node references
            if isinstance(node, LoopNode):
                for do_node_id in node.do:
                    if do_node_id not in node_ids:
                        errors.append(
                            f"Loop node '{node.id}' references unknown 'do' node '{do_node_id}'"
                        )

            # Check parallel node references
            if isinstance(node, ParallelNode):
                for parallel_id in node.nodes:
                    if parallel_id not in node_ids:
                        errors.append(
                            f"Parallel node '{node.id}' references unknown node '{parallel_id}'"
                        )

        if errors:
            raise ValueError("\n".join(errors))

        return self

    @model_validator(mode="after")
    def validate_no_duplicate_node_ids(self) -> Workflow:
        """Ensure all node IDs are unique."""
        node_ids = [n.id for n in self.nodes]
        duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
        if duplicates:
            unique_duplicates = list(set(duplicates))
            raise ValueError(f"Duplicate node IDs found: {unique_duplicates}")
        return self

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_node_ids(self) -> set[str]:
        """Get all node IDs."""
        return {n.id for n in self.nodes}

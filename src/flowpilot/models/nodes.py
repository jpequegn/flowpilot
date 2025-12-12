"""Node models for FlowPilot workflows."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class BaseNode(BaseModel):
    """Base class for all workflow nodes."""

    id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Unique node identifier (lowercase, alphanumeric, hyphens)",
    )
    depends_on: list[str] = Field(default_factory=list, description="Node IDs this node depends on")


class ShellNode(BaseNode):
    """Execute a shell command."""

    type: Literal["shell"]
    command: str = Field(..., description="Shell command to execute")
    working_dir: str | None = Field(default=None, description="Working directory")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    timeout: int = Field(default=60, ge=1, description="Timeout in seconds")


class HttpNode(BaseNode):
    """Make an HTTP request."""

    type: Literal["http"]
    url: str = Field(..., description="URL to request")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        default="GET", description="HTTP method"
    )
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    body: str | dict[str, Any] | None = Field(default=None, description="Request body")
    timeout: int = Field(default=30, ge=1, description="Timeout in seconds")


class FileReadNode(BaseNode):
    """Read content from a file."""

    type: Literal["file-read"]
    path: str = Field(..., description="File path to read")
    encoding: str = Field(default="utf-8", description="File encoding")


class FileWriteNode(BaseNode):
    """Write content to a file."""

    type: Literal["file-write"]
    path: str = Field(..., description="File path to write")
    content: str = Field(..., description="Content to write")
    mode: Literal["write", "append"] = Field(default="write", description="Write mode")
    encoding: str = Field(default="utf-8", description="File encoding")


class ConditionNode(BaseNode):
    """Branch workflow based on a condition."""

    type: Literal["condition"]
    if_expr: str = Field(..., alias="if", description="Condition expression to evaluate")
    then: str = Field(..., description="Node ID to execute if condition is true")
    else_node: str | None = Field(
        default=None, alias="else", description="Node ID to execute if condition is false"
    )


class LoopNode(BaseNode):
    """Iterate over items."""

    type: Literal["loop"]
    for_each: str = Field(..., alias="for", description="Expression yielding items to iterate")
    as_var: str = Field(default="item", alias="as", description="Variable name for each item")
    do: str = Field(..., description="Node ID to execute for each item")


class DelayNode(BaseNode):
    """Wait for a duration."""

    type: Literal["delay"]
    duration: str = Field(..., description="Duration like '5s', '1m', '30s'")


class ParallelNode(BaseNode):
    """Execute nodes in parallel."""

    type: Literal["parallel"]
    nodes: list[str] = Field(..., description="Node IDs to execute in parallel")
    fail_fast: bool = Field(default=True, description="Stop on first failure")


class ClaudeCliNode(BaseNode):
    """Execute a prompt using Claude Code CLI."""

    type: Literal["claude-cli"]
    prompt: str = Field(..., description="Prompt to send to Claude")
    model: Literal["sonnet", "opus", "haiku"] | None = Field(
        default=None, description="Model to use"
    )
    working_dir: str | None = Field(default=None, description="Working directory context")
    timeout: int = Field(default=300, ge=1, description="Timeout in seconds")
    output_format: Literal["text", "json"] = Field(default="text", description="Output format")


class ClaudeApiNode(BaseNode):
    """Call Claude API directly."""

    type: Literal["claude-api"]
    prompt: str = Field(..., description="Prompt to send")
    model: str = Field(default="claude-sonnet-4-20250514", description="Model ID")
    system: str | None = Field(default=None, description="System prompt")
    max_tokens: int = Field(default=4096, ge=1, description="Maximum tokens")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0, description="Temperature")
    timeout: int = Field(default=120, ge=1, description="Timeout in seconds")
    output_format: Literal["text", "json"] = Field(default="text", description="Output format")


# Union type for all nodes with discriminator
Node = Annotated[
    ShellNode
    | HttpNode
    | FileReadNode
    | FileWriteNode
    | ConditionNode
    | LoopNode
    | DelayNode
    | ParallelNode
    | ClaudeCliNode
    | ClaudeApiNode,
    Field(discriminator="type"),
]

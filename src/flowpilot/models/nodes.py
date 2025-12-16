"""Node models for FlowPilot workflows."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RetryConfig(BaseModel):
    """Retry configuration for nodes."""

    model_config = ConfigDict(populate_by_name=True)

    max_attempts: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts")
    initial_delay: float = Field(
        default=1.0, ge=0.1, le=60.0, description="Initial delay in seconds"
    )
    max_delay: float = Field(default=60.0, ge=1.0, le=600.0, description="Maximum delay in seconds")
    exponential_base: float = Field(
        default=2.0, ge=1.0, le=4.0, description="Exponential backoff base"
    )
    jitter: bool = Field(default=True, description="Add randomness to delays")
    retry_on_transient: bool = Field(default=True, description="Retry on transient errors")
    retry_on_resource: bool = Field(
        default=True, description="Retry on resource errors (rate limits)"
    )


class BaseNode(BaseModel):
    """Base class for all workflow nodes."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Unique node identifier (lowercase, alphanumeric, hyphens)",
    )
    depends_on: list[str] = Field(default_factory=list, description="Node IDs this node depends on")
    retry: RetryConfig | None = Field(default=None, description="Retry configuration")
    fallback: str | None = Field(default=None, description="Node ID to execute on failure")
    continue_on_error: bool = Field(default=False, description="Don't stop workflow on error")


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
    index_var: str = Field(default="index", description="Variable name for current index")
    do: list[str] = Field(..., description="Node IDs to execute for each item")
    max_iterations: int | None = Field(
        default=None, ge=1, description="Maximum iterations (safety limit)"
    )
    break_if: str | None = Field(default=None, description="Expression to break loop early")


class DelayNode(BaseNode):
    """Wait for a duration or until a specific time."""

    type: Literal["delay"]
    duration: str | None = Field(default=None, description="Duration like '5s', '1m', '2h', '1d'")
    until: str | None = Field(
        default=None, description="ISO datetime or template expression to wait until"
    )


class ParallelNode(BaseNode):
    """Execute nodes in parallel."""

    type: Literal["parallel"]
    nodes: list[str] = Field(..., description="Node IDs to execute in parallel")
    fail_fast: bool = Field(default=True, description="Stop on first failure")
    max_concurrency: int | None = Field(
        default=None, ge=1, description="Limit simultaneous executions"
    )
    timeout: int | None = Field(
        default=None, ge=1, description="Timeout in seconds for entire parallel group"
    )


class ClaudeCliNode(BaseNode):
    """Execute a prompt using Claude Code CLI."""

    type: Literal["claude-cli"]
    prompt: str = Field(..., description="Prompt to send to Claude (Jinja2 templated)")
    model: Literal["sonnet", "opus", "haiku"] | None = Field(
        default=None, description="Model to use"
    )
    working_dir: str | None = Field(default=None, description="Working directory context")
    timeout: int = Field(default=300, ge=1, description="Timeout in seconds")
    output_format: Literal["text", "json", "stream-json"] = Field(
        default="text", description="Output format"
    )
    max_tokens: int | None = Field(default=None, ge=1, description="Maximum tokens for response")
    system_prompt: str | None = Field(default=None, description="Additional system context")
    allowed_tools: list[str] | None = Field(
        default=None, description="Restrict tool access to these tools"
    )
    no_tools: bool = Field(default=False, description="Disable all tools")
    session_id: str | None = Field(default=None, description="Resume previous conversation")
    save_session: bool = Field(default=False, description="Save session for continuation")


class ClaudeApiNode(BaseNode):
    """Call Claude API directly via Anthropic SDK."""

    type: Literal["claude-api"]
    prompt: str = Field(..., description="User message (Jinja2 templated)")

    # Model configuration
    model: str = Field(default="claude-sonnet-4-20250514", description="Claude model ID")

    # System prompt
    system: str | None = Field(default=None, description="System prompt")

    # Generation parameters
    max_tokens: int = Field(default=4096, ge=1, description="Maximum tokens for response")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0, description="Temperature")
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, description="Top-p sampling")
    top_k: int | None = Field(default=None, ge=1, description="Top-k sampling")

    # Output control
    stop_sequences: list[str] | None = Field(default=None, description="Stop sequences")
    output_format: Literal["text", "json"] = Field(default="text", description="Output format")
    json_schema: dict[str, Any] | None = Field(default=None, description="JSON schema for output")

    # Execution
    timeout: int = Field(default=120, ge=1, description="API timeout in seconds")

    # Advanced
    metadata: dict[str, str] | None = Field(default=None, description="Request metadata")

    # Multi-turn (within same node execution)
    messages: list[dict[str, Any]] | None = Field(
        default=None, description="Override with full message history"
    )


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

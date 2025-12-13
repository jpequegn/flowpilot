"""Node executor framework for FlowPilot workflows."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from flowpilot.models import (
    BaseNode,
    ClaudeApiNode,
    ClaudeCliNode,
    ConditionNode,
    DelayNode,
    FileReadNode,
    FileWriteNode,
    HttpNode,
    LoopNode,
    ParallelNode,
    ShellNode,
)

from .context import NodeResult

if TYPE_CHECKING:
    from .context import ExecutionContext

# Type alias for node types
NodeType = str


class NodeExecutor(ABC):
    """Abstract base class for node executors."""

    @abstractmethod
    async def execute(
        self,
        node: BaseNode,
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute a node and return result.

        Args:
            node: The node to execute.
            context: The execution context with inputs and previous results.

        Returns:
            NodeResult with execution outcome.
        """

    async def execute_with_timeout(
        self,
        node: BaseNode,
        context: ExecutionContext,
        timeout: int,
    ) -> NodeResult:
        """Execute a node with timeout.

        Args:
            node: The node to execute.
            context: The execution context.
            timeout: Timeout in seconds.

        Returns:
            NodeResult with execution outcome or timeout error.
        """
        try:
            return await asyncio.wait_for(
                self.execute(node, context),
                timeout=timeout,
            )
        except TimeoutError:
            return NodeResult.error(f"Node execution timed out after {timeout}s")


class ExecutorRegistry:
    """Registry for node executors."""

    _executors: ClassVar[dict[NodeType, type[NodeExecutor]]] = {}
    _instances: ClassVar[dict[NodeType, NodeExecutor]] = {}

    @classmethod
    def register(cls, node_type: NodeType) -> Any:
        """Register an executor for a node type.

        Args:
            node_type: The type of node this executor handles.

        Returns:
            Decorator function.
        """

        def decorator(executor_cls: type[NodeExecutor]) -> type[NodeExecutor]:
            cls._executors[node_type] = executor_cls
            return executor_cls

        return decorator

    @classmethod
    def get(cls, node_type: NodeType) -> NodeExecutor:
        """Get an executor instance for a node type.

        Args:
            node_type: The type of node to get executor for.

        Returns:
            NodeExecutor instance.

        Raises:
            ValueError: If no executor is registered for the node type.
        """
        if node_type not in cls._executors:
            raise ValueError(f"No executor registered for node type: {node_type}")

        # Lazy instantiation with caching
        if node_type not in cls._instances:
            cls._instances[node_type] = cls._executors[node_type]()

        return cls._instances[node_type]

    @classmethod
    def has_executor(cls, node_type: NodeType) -> bool:
        """Check if an executor is registered for a node type."""
        return node_type in cls._executors

    @classmethod
    def clear(cls) -> None:
        """Clear all registered executors (for testing)."""
        cls._executors.clear()
        cls._instances.clear()


def get_node_timeout(node: BaseNode) -> int:
    """Get the timeout for a node based on its type.

    Args:
        node: The node to get timeout for.

    Returns:
        Timeout in seconds.
    """
    if isinstance(node, ShellNode | HttpNode | ClaudeCliNode | ClaudeApiNode):
        return node.timeout
    # Default timeouts for other node types
    if isinstance(node, FileReadNode | FileWriteNode):
        return 30
    if isinstance(node, DelayNode):
        # Parse duration string to get timeout (add buffer)
        return 3600  # Max 1 hour for delay
    if isinstance(node, ConditionNode | LoopNode | ParallelNode):
        return 300  # Control flow nodes get 5 minutes
    return 60  # Default timeout

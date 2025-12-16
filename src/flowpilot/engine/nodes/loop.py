"""Loop node executor for FlowPilot."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import LoopNode

logger = logging.getLogger(__name__)


@ExecutorRegistry.register("loop")
class LoopExecutor(NodeExecutor):
    """Execute loop iterations over a collection."""

    async def execute(
        self,
        node: LoopNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute a loop over items.

        The loop executor resolves the for_each expression, iterates over items,
        and executes child nodes for each iteration. Loop variables (item, index)
        are made available to child nodes through the context.

        Args:
            node: The loop node to execute.
            context: The execution context.

        Returns:
            NodeResult with loop execution results.
        """
        started_at = datetime.now()

        try:
            # Get template context for expression evaluation
            ctx = context.get_template_context()

            # Resolve the for_each expression to get items
            items = self._resolve_expression(node.for_each, ctx)

            if items is None:
                return NodeResult(
                    status="error",
                    error_message=f"for_each expression '{node.for_each}' resolved to None",
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            if not isinstance(items, (list, tuple)):
                return NodeResult(
                    status="error",
                    error_message=f"for_each must resolve to a list or tuple, got {type(items).__name__}",
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            # Handle empty arrays gracefully
            if len(items) == 0:
                logger.debug(f"Loop {node.id}: empty collection, no iterations")
                return NodeResult(
                    status="success",
                    output={"iterations": 0, "items_processed": []},
                    data={
                        "iterations": 0,
                        "total_items": 0,
                        "items_processed": [],
                        "break_triggered": False,
                        "child_nodes": node.do,
                    },
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            # Apply max_iterations limit
            max_iter = node.max_iterations if node.max_iterations else len(items)
            items_to_process = list(items[:max_iter])
            total_items = len(items)

            logger.debug(
                f"Loop {node.id}: processing {len(items_to_process)} of {total_items} items"
            )

            # Return loop configuration for the runner to execute
            # The actual iteration execution is handled by the runner
            return NodeResult(
                status="success",
                output={
                    "iterations": len(items_to_process),
                    "total_items": total_items,
                },
                data={
                    # Loop execution data for the runner
                    "loop_items": items_to_process,
                    "as_var": node.as_var,
                    "index_var": node.index_var,
                    "child_nodes": node.do,
                    "break_if": node.break_if,
                    # Metadata
                    "total_items": total_items,
                    "max_iterations": node.max_iterations,
                    "iterations_planned": len(items_to_process),
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        except ValueError as e:
            return NodeResult(
                status="error",
                error_message=f"Loop expression evaluation failed: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            logger.exception(f"Loop {node.id}: unexpected error")
            return NodeResult(
                status="error",
                error_message=f"Loop error: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

    def _resolve_expression(self, expr: str, context: dict[str, Any]) -> Any:
        """Safely resolve an expression to get items.

        Args:
            expr: Expression like 'nodes.get_files.data.files' or 'inputs.items'.
            context: Template context dictionary.

        Returns:
            Resolved value.

        Raises:
            ValueError: If expression is invalid or uses disallowed names.
        """
        # Define allowed built-in names for safe evaluation
        # These are dangerous functions that should never be allowed
        dangerous_names = {
            "__import__",
            "exec",
            "eval",
            "compile",
            "open",
            "input",
            "breakpoint",
            "globals",
            "locals",
            "vars",
            "dir",
            "getattr",
            "setattr",
            "delattr",
            "hasattr",
        }

        allowed_builtins: dict[str, Any] = {
            "True": True,
            "False": False,
            "None": None,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "min": min,
            "max": max,
            "sum": sum,
            "any": any,
            "all": all,
            "abs": abs,
            "round": round,
        }

        # Merge context with allowed builtins
        eval_context = {**allowed_builtins, **context}

        # Compile the expression
        try:
            code = compile(expr, "<loop_expression>", "eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid syntax in for_each: {e}") from e

        # Check for dangerous names (only check top-level names, not attributes)
        for name in code.co_names:
            if name in dangerous_names:
                raise ValueError(f"Name '{name}' is not allowed in for_each expression")

        # Evaluate with restricted builtins
        try:
            return eval(code, {"__builtins__": {}}, eval_context)
        except Exception as e:
            raise ValueError(f"Expression evaluation failed: {e}") from e

    def _evaluate_break_condition(self, expr: str, context: dict[str, Any]) -> bool:
        """Evaluate a break condition expression.

        Args:
            expr: Break condition expression.
            context: Template context with loop variables.

        Returns:
            True if loop should break.
        """
        allowed_names: dict[str, Any] = {
            "True": True,
            "False": False,
            "None": None,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "any": any,
            "all": all,
            **context,
        }

        try:
            code = compile(expr, "<break_condition>", "eval")
        except SyntaxError:
            return False

        for name in code.co_names:
            if name not in allowed_names:
                return False

        try:
            return bool(eval(code, {"__builtins__": {}}, allowed_names))
        except Exception:
            return False

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)

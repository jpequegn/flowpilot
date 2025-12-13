"""Condition node executor for FlowPilot."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import ConditionNode


@ExecutorRegistry.register("condition")
class ConditionExecutor(NodeExecutor):
    """Evaluate conditions and determine next node."""

    async def execute(
        self,
        node: ConditionNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Evaluate a condition and return the next node to execute.

        Args:
            node: The condition node to execute.
            context: The execution context.

        Returns:
            NodeResult with condition result and next node.
        """
        started_at = datetime.now()

        try:
            # Get template context for evaluation
            ctx = context.get_template_context()

            # Safely evaluate the condition
            result = self._safe_eval(node.if_expr, ctx)

            # Determine next node
            next_node = node.then if result else node.else_node

            return NodeResult(
                status="success",
                output=str(result),
                data={
                    "condition": node.if_expr,
                    "result": bool(result),
                    "next_node": next_node,
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        except ValueError as e:
            return NodeResult(
                status="error",
                error_message=f"Condition evaluation failed: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return NodeResult(
                status="error",
                error_message=f"Condition error: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

    def _safe_eval(self, expr: str, context: dict[str, Any]) -> bool:
        """Safely evaluate a Python expression.

        Args:
            expr: The expression to evaluate.
            context: Context dictionary for variable access.

        Returns:
            Boolean result of the expression.

        Raises:
            ValueError: If expression uses disallowed names.
        """
        # Define allowed built-in names
        allowed_names: dict[str, Any] = {
            # Boolean and None
            "True": True,
            "False": False,
            "None": None,
            # Type conversions
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            # Collection operations
            "any": any,
            "all": all,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            # String operations
            "lower": str.lower,
            "upper": str.upper,
            # Context variables
            **context,
        }

        # Compile the expression
        try:
            code = compile(expr, "<condition>", "eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid syntax: {e}") from e

        # Check for disallowed names
        for name in code.co_names:
            if name not in allowed_names:
                raise ValueError(f"Name '{name}' is not allowed in conditions")

        # Evaluate with restricted builtins
        try:
            result = eval(code, {"__builtins__": {}}, allowed_names)
            return bool(result)
        except Exception as e:
            raise ValueError(f"Evaluation failed: {e}") from e

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)

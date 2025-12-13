"""HTTP node executor for FlowPilot."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import HttpNode


@ExecutorRegistry.register("http")
class HttpExecutor(NodeExecutor):
    """Execute HTTP requests."""

    async def execute(
        self,
        node: HttpNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute an HTTP request.

        Args:
            node: The HTTP node to execute.
            context: The execution context.

        Returns:
            NodeResult with response data.
        """
        started_at = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=node.timeout) as client:
                # Prepare request body
                content: str | None = None
                json_body: dict[str, Any] | None = None

                if node.body is not None:
                    if isinstance(node.body, dict):
                        json_body = node.body
                    else:
                        content = str(node.body)

                # Make request
                response = await client.request(
                    method=node.method,
                    url=node.url,
                    headers=node.headers,
                    content=content,
                    json=json_body,
                )

                # Try to parse JSON response
                response_data: dict[str, Any]
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {"text": response.text}

                # Build result
                data = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_data,
                }

                if response.is_success:
                    return NodeResult(
                        status="success",
                        output=response.text,
                        data=data,
                        duration_ms=self._duration_ms(started_at),
                        started_at=started_at,
                        finished_at=datetime.now(),
                    )
                else:
                    return NodeResult(
                        status="error",
                        output=response.text,
                        data=data,
                        error_message=f"HTTP {response.status_code}: {response.reason_phrase}",
                        duration_ms=self._duration_ms(started_at),
                        started_at=started_at,
                        finished_at=datetime.now(),
                    )

        except httpx.TimeoutException:
            return NodeResult(
                status="error",
                error_message=f"Request timed out after {node.timeout}s",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except httpx.ConnectError as e:
            return NodeResult(
                status="error",
                error_message=f"Connection failed: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return NodeResult(
                status="error",
                error_message=str(e),
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)

"""File read node executor for FlowPilot."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import FileReadNode


@ExecutorRegistry.register("file-read")
class FileReadExecutor(NodeExecutor):
    """Read file contents."""

    async def execute(
        self,
        node: FileReadNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Read contents of a file.

        Args:
            node: The file read node to execute.
            context: The execution context.

        Returns:
            NodeResult with file contents.
        """
        started_at = datetime.now()

        # Expand path
        path = self._expand_path(node.path)

        try:
            # Read file content
            content = path.read_text(encoding=node.encoding)
            stat = path.stat()

            return NodeResult(
                status="success",
                output=content,
                data={
                    "path": str(path),
                    "size": stat.st_size,
                    "lines": len(content.splitlines()),
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        except FileNotFoundError:
            return NodeResult(
                status="error",
                error_message=f"File not found: {path}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except PermissionError:
            return NodeResult(
                status="error",
                error_message=f"Permission denied: {path}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except UnicodeDecodeError as e:
            return NodeResult(
                status="error",
                error_message=f"Encoding error ({node.encoding}): {e}",
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
    def _expand_path(path: str) -> Path:
        """Expand ~ and environment variables in path."""
        expanded = os.path.expandvars(os.path.expanduser(path))
        return Path(expanded)

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)

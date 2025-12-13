"""File write node executor for FlowPilot."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import FileWriteNode


@ExecutorRegistry.register("file-write")
class FileWriteExecutor(NodeExecutor):
    """Write content to files."""

    async def execute(
        self,
        node: FileWriteNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Write content to a file.

        Args:
            node: The file write node to execute.
            context: The execution context.

        Returns:
            NodeResult with file path.
        """
        started_at = datetime.now()

        # Expand path
        path = self._expand_path(node.path)

        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write content based on mode
            if node.mode == "append":
                with open(path, "a", encoding=node.encoding) as f:
                    f.write(node.content)
            else:
                path.write_text(node.content, encoding=node.encoding)

            stat = path.stat()

            return NodeResult(
                status="success",
                output=str(path),
                data={
                    "path": str(path),
                    "size": stat.st_size,
                    "mode": node.mode,
                },
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
        except OSError as e:
            return NodeResult(
                status="error",
                error_message=f"OS error writing file: {e}",
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

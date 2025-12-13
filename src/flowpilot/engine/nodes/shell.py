"""Shell node executor for FlowPilot."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import ShellNode


@ExecutorRegistry.register("shell")
class ShellExecutor(NodeExecutor):
    """Execute shell commands."""

    async def execute(
        self,
        node: ShellNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute a shell command.

        Args:
            node: The shell node to execute.
            context: The execution context.

        Returns:
            NodeResult with command output.
        """
        started_at = datetime.now()

        # Expand paths and prepare environment
        working_dir = self._expand_path(node.working_dir) if node.working_dir else None
        env = {**os.environ, **node.env}

        try:
            # Create subprocess
            proc = await asyncio.create_subprocess_shell(
                node.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )

            # Wait for completion with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=node.timeout,
                )
            except TimeoutError:
                # Kill the process on timeout
                proc.kill()
                await proc.wait()
                return NodeResult(
                    status="error",
                    error_message=f"Command timed out after {node.timeout}s",
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            # Decode output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0

            # Build result
            if exit_code == 0:
                return NodeResult(
                    status="success",
                    stdout=stdout,
                    stderr=stderr,
                    output=stdout.strip(),
                    data={"exit_code": exit_code},
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )
            else:
                return NodeResult(
                    status="error",
                    stdout=stdout,
                    stderr=stderr,
                    output=stdout.strip(),
                    data={"exit_code": exit_code},
                    error_message=f"Command exited with code {exit_code}",
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

        except FileNotFoundError as e:
            return NodeResult(
                status="error",
                error_message=f"Working directory not found: {e}",
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

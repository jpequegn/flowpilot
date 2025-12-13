"""Claude CLI node executor for FlowPilot."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import ClaudeCliNode


class ClaudeCliNotFoundError(RuntimeError):
    """Raised when the Claude CLI binary is not found."""


@ExecutorRegistry.register("claude-cli")
class ClaudeCliExecutor(NodeExecutor):
    """Execute prompts via Claude Code CLI."""

    def __init__(self) -> None:
        """Initialize the executor."""
        self._claude_path: str | None = None

    def _find_claude_binary(self) -> str:
        """Find the claude CLI binary.

        Returns:
            Path to the claude binary.

        Raises:
            ClaudeCliNotFoundError: If claude CLI is not found.
        """
        if self._claude_path:
            return self._claude_path

        # Check common locations
        locations = [
            shutil.which("claude"),
            "/usr/local/bin/claude",
            os.path.expanduser("~/.claude/bin/claude"),
            os.path.expanduser("~/bin/claude"),
            "/opt/homebrew/bin/claude",
        ]

        for loc in locations:
            if loc and Path(loc).exists():
                self._claude_path = loc
                return loc

        raise ClaudeCliNotFoundError(
            "Claude CLI not found. Install from: https://claude.ai/download"
        )

    async def execute(
        self,
        node: ClaudeCliNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute a prompt via Claude CLI.

        Args:
            node: The claude-cli node to execute.
            context: The execution context.

        Returns:
            NodeResult with Claude's response.
        """
        started_at = datetime.now()

        # Find claude binary
        try:
            claude_path = self._find_claude_binary()
        except ClaudeCliNotFoundError as e:
            return NodeResult(
                status="error",
                error_message=str(e),
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        # Build command arguments
        cmd = [claude_path]

        # Add prompt with --print for non-interactive mode
        cmd.extend(["--print", node.prompt])

        # Model selection
        if node.model:
            cmd.extend(["--model", node.model])

        # Output format
        if node.output_format == "json":
            cmd.append("--output-format=json")
        elif node.output_format == "stream-json":
            cmd.append("--output-format=stream-json")

        # Max tokens
        if node.max_tokens:
            cmd.extend(["--max-tokens", str(node.max_tokens)])

        # System prompt
        if node.system_prompt:
            cmd.extend(["--system-prompt", node.system_prompt])

        # Tool restrictions
        if node.no_tools:
            cmd.append("--no-tools")
        elif node.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(node.allowed_tools)])

        # Session management
        if node.session_id:
            cmd.extend(["--resume", node.session_id])

        # Working directory
        working_dir = self._expand_path(node.working_dir) if node.working_dir else None

        # Environment - pass through with FlowPilot context
        env = os.environ.copy()
        env["FLOWPILOT_EXECUTION_ID"] = context.execution_id
        env["FLOWPILOT_WORKFLOW"] = context.workflow_name

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=node.timeout,
                )
            except TimeoutError:
                # Graceful termination first
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()

                return NodeResult(
                    status="error",
                    error_message=f"Claude CLI timed out after {node.timeout}s",
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0

            # Parse output based on format
            output, data = self._parse_output(stdout, node.output_format)

            # Extract session ID if saving
            if node.save_session:
                session_id = self._extract_session_id(stderr)
                if session_id:
                    data["session_id"] = session_id

            if exit_code == 0:
                return NodeResult(
                    status="success",
                    stdout=stdout,
                    stderr=stderr,
                    output=output,
                    data=data,
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )
            else:
                return NodeResult(
                    status="error",
                    stdout=stdout,
                    stderr=stderr,
                    output=output,
                    data=data,
                    error_message=f"Claude CLI exited with code {exit_code}",
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(),
                )

        except FileNotFoundError:
            return NodeResult(
                status="error",
                error_message=f"Claude CLI not found at: {claude_path}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return NodeResult(
                status="error",
                error_message=f"Claude CLI execution failed: {e!s}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

    def _parse_output(
        self,
        stdout: str,
        output_format: str,
    ) -> tuple[str, dict[str, Any]]:
        """Parse Claude CLI output based on format.

        Args:
            stdout: Raw stdout from Claude CLI.
            output_format: Expected output format.

        Returns:
            Tuple of (output text, parsed data dict).
        """
        if output_format == "json":
            try:
                data = json.loads(stdout)
                # Extract main response text from JSON structure
                output = data.get("result", {}).get("text", stdout)
                return output, data
            except json.JSONDecodeError:
                return stdout.strip(), {"raw": stdout}

        elif output_format == "stream-json":
            # Parse streaming JSON (newline-delimited)
            lines = []
            events = []
            for line in stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    events.append(event)
                    if event.get("type") == "text":
                        lines.append(event.get("text", ""))
                except json.JSONDecodeError:
                    lines.append(line)

            return "".join(lines), {"events": events}

        else:  # text
            return stdout.strip(), {}

    @staticmethod
    def _extract_session_id(stderr: str) -> str | None:
        """Extract session ID from stderr if present.

        Args:
            stderr: Stderr output from Claude CLI.

        Returns:
            Session ID if found, None otherwise.
        """
        # Claude CLI may output session info to stderr
        # Session IDs can contain letters and numbers with hyphens
        match = re.search(r"Session ID: ([a-zA-Z0-9-]+)", stderr, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _expand_path(path: str) -> Path:
        """Expand ~ and environment variables in path."""
        expanded = os.path.expandvars(os.path.expanduser(path))
        return Path(expanded)

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)

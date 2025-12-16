"""Serve command for FlowPilot CLI.

Provides daemon mode for running the FlowPilot server with proper
process management, signal handling, and log rotation.
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import typer
import uvicorn

from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir

if TYPE_CHECKING:
    from types import FrameType

logger = logging.getLogger(__name__)


def get_pid_file() -> Path:
    """Get the path to the PID file."""
    return get_flowpilot_dir() / "flowpilot.pid"


def get_log_file() -> Path:
    """Get the path to the server log file."""
    log_dir = get_flowpilot_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "server.log"


def read_pid() -> int | None:
    """Read the PID from the PID file.

    Returns:
        The PID if the file exists and contains a valid PID, None otherwise.
    """
    pid_file = get_pid_file()
    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        # Check if process is actually running
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # Invalid PID or process not running
        pid_file.unlink(missing_ok=True)
        return None


def write_pid(pid: int) -> None:
    """Write the PID to the PID file.

    Args:
        pid: The process ID to write.
    """
    pid_file = get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))


def remove_pid_file() -> None:
    """Remove the PID file."""
    pid_file = get_pid_file()
    pid_file.unlink(missing_ok=True)


def is_server_running() -> tuple[bool, int | None]:
    """Check if the server is running.

    Returns:
        Tuple of (is_running, pid).
    """
    pid = read_pid()
    return (pid is not None, pid)


def stop_server(pid: int, timeout: int = 10) -> bool:
    """Stop a running server by PID.

    Args:
        pid: The process ID to stop.
        timeout: Maximum seconds to wait for graceful shutdown.

    Returns:
        True if server was stopped, False if it was already not running.
    """
    try:
        # First try graceful shutdown with SIGTERM
        os.kill(pid, signal.SIGTERM)

        # Wait for process to exit
        for _ in range(timeout):
            time.sleep(1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                # Process has exited
                remove_pid_file()
                return True

        # Force kill if still running
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        remove_pid_file()
        return True

    except ProcessLookupError:
        # Process already dead
        remove_pid_file()
        return False


def daemonize() -> None:
    """Daemonize the current process using double fork.

    This detaches the process from the terminal and creates a proper daemon.
    """
    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process exits
            sys.exit(0)
    except OSError as e:
        console.print(f"[red]Error:[/] First fork failed: {e}")
        sys.exit(1)

    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            # First child exits
            sys.exit(0)
    except OSError as e:
        console.print(f"[red]Error:[/] Second fork failed: {e}")
        sys.exit(1)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    log_file = get_log_file()
    with (
        open("/dev/null", "rb") as null_in,
        open(log_file, "a+b") as log_out,
    ):
        os.dup2(null_in.fileno(), sys.stdin.fileno())
        os.dup2(log_out.fileno(), sys.stdout.fileno())
        os.dup2(log_out.fileno(), sys.stderr.fileno())


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""

    def handle_signal(signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        remove_pid_file()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)


def setup_logging(log_file: Path, debug: bool = False) -> None:
    """Set up logging for the daemon.

    Args:
        log_file: Path to the log file.
        debug: Enable debug logging.
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
        ],
    )


def run_server(host: str, port: int, reload: bool = False) -> None:
    """Run the uvicorn server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        reload: Enable auto-reload (for development).
    """
    # Import here to avoid circular imports
    from flowpilot.api.app import create_app
    from flowpilot.cli.utils import get_workflows_dir
    from flowpilot.engine.runner import WorkflowRunner
    from flowpilot.storage.database import Database

    # Initialize database and runner
    db_path = get_flowpilot_dir() / "flowpilot.db"
    db = Database(db_path)
    db.create_tables()

    workflows_dir = get_workflows_dir()
    runner = WorkflowRunner(db=db)

    # Create the FastAPI app
    app_instance = create_app(
        workflows_dir=workflows_dir,
        runner=runner,
        enable_cors=True,
    )

    # Run uvicorn
    uvicorn.run(
        app_instance,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host to bind to",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port to bind to",
    ),
    daemon: bool = typer.Option(
        False,
        "--daemon",
        "-d",
        help="Run as background daemon",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload (development mode)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging",
    ),
) -> None:
    """Start the FlowPilot API server.

    Runs the API server for webhooks, execution management, and workflow operations.

    Examples:
        flowpilot serve                  # Start in foreground
        flowpilot serve --daemon         # Start as background daemon
        flowpilot serve --port 8080      # Custom port
        flowpilot serve --reload         # Development mode with auto-reload
    """
    # Check if server is already running
    running, existing_pid = is_server_running()
    if running:
        console.print(f"[yellow]Server already running (PID: {existing_pid})[/]")
        console.print("Use [cyan]flowpilot stop[/] to stop it first.")
        raise typer.Exit(1)

    if daemon:
        # Daemon mode
        console.print(f"[cyan]Starting FlowPilot server in daemon mode on {host}:{port}...[/]")

        daemonize()

        # Now we're in the daemon process
        log_file = get_log_file()
        setup_logging(log_file, debug)
        setup_signal_handlers()

        # Write PID file
        write_pid(os.getpid())
        atexit.register(remove_pid_file)

        logger.info(f"FlowPilot server starting on {host}:{port}")
        run_server(host, port, reload=False)  # No reload in daemon mode
    else:
        # Foreground mode
        console.print(f"[cyan]Starting FlowPilot server on {host}:{port}...[/]")
        console.print("[dim]Press Ctrl+C to stop[/]")
        console.print()

        # Write PID file even in foreground mode
        write_pid(os.getpid())
        atexit.register(remove_pid_file)

        try:
            run_server(host, port, reload)
        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped.[/]")
        finally:
            remove_pid_file()


@app.command()
def stop() -> None:
    """Stop the running FlowPilot server.

    Sends SIGTERM to the running server process for graceful shutdown.
    If the server doesn't stop within 10 seconds, it will be forcefully killed.

    Examples:
        flowpilot stop
    """
    running, pid = is_server_running()

    if not running or pid is None:
        console.print("[yellow]Server is not running.[/]")
        raise typer.Exit(0)

    console.print(f"[cyan]Stopping FlowPilot server (PID: {pid})...[/]")

    if stop_server(pid):
        console.print("[green]Server stopped successfully.[/]")
    else:
        console.print("[yellow]Server was already stopped.[/]")


@app.command()
def restart(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host to bind to",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port to bind to",
    ),
    daemon: bool = typer.Option(
        True,
        "--daemon/--no-daemon",
        "-d",
        help="Run as background daemon (default: true)",
    ),
) -> None:
    """Restart the FlowPilot server.

    Stops any running server and starts a new one.
    By default, starts in daemon mode.

    Examples:
        flowpilot restart
        flowpilot restart --port 9000
        flowpilot restart --no-daemon
    """
    running, pid = is_server_running()

    if running and pid is not None:
        console.print(f"[cyan]Stopping FlowPilot server (PID: {pid})...[/]")
        stop_server(pid)
        console.print("[green]Server stopped.[/]")
        time.sleep(1)  # Brief pause before restart

    console.print()

    if daemon:
        console.print(f"[cyan]Starting FlowPilot server in daemon mode on {host}:{port}...[/]")
        daemonize()

        log_file = get_log_file()
        setup_logging(log_file)
        setup_signal_handlers()

        write_pid(os.getpid())
        atexit.register(remove_pid_file)

        logger.info(f"FlowPilot server starting on {host}:{port}")
        run_server(host, port, reload=False)
    else:
        console.print(f"[cyan]Starting FlowPilot server on {host}:{port}...[/]")
        console.print("[dim]Press Ctrl+C to stop[/]")
        console.print()

        write_pid(os.getpid())
        atexit.register(remove_pid_file)

        try:
            run_server(host, port)
        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped.[/]")
        finally:
            remove_pid_file()


@app.command()
def status(
    server: bool = typer.Option(
        False,
        "--server",
        "-s",
        help="Check server status",
    ),
) -> None:
    """Show FlowPilot status.

    Displays information about the FlowPilot installation and running services.

    Examples:
        flowpilot status             # Show general status
        flowpilot status --server    # Check if server is running
    """
    flowpilot_dir = get_flowpilot_dir()

    console.print("[bold]FlowPilot Status[/]")
    console.print()

    # FlowPilot directory
    console.print(f"[dim]FlowPilot directory:[/] {flowpilot_dir}")

    if not flowpilot_dir.exists():
        console.print("[yellow]FlowPilot not initialized.[/]")
        console.print("Run [cyan]flowpilot init[/] to set up FlowPilot.")
        return

    # Database
    db_file = flowpilot_dir / "flowpilot.db"
    if db_file.exists():
        size_kb = db_file.stat().st_size / 1024
        console.print(f"[dim]Database:[/] {db_file} ({size_kb:.1f} KB)")
    else:
        console.print("[dim]Database:[/] [yellow]Not found[/]")

    # Workflows directory
    workflows_dir = flowpilot_dir / "workflows"
    if workflows_dir.exists():
        workflow_count = len(list(workflows_dir.glob("*.yaml")))
        console.print(f"[dim]Workflows:[/] {workflow_count} workflow(s) in {workflows_dir}")
    else:
        console.print("[dim]Workflows:[/] [yellow]Directory not found[/]")

    # Server status
    if server:
        console.print()
        running, pid = is_server_running()
        if running:
            console.print(f"[green]Server is running[/] (PID: {pid})")

            # Try to get server info
            log_file = get_log_file()
            if log_file.exists():
                console.print(f"[dim]Log file:[/] {log_file}")
        else:
            console.print("[yellow]Server is not running[/]")
            console.print("Start with [cyan]flowpilot serve --daemon[/]")

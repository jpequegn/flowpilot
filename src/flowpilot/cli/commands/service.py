"""Service commands for FlowPilot CLI.

Provides launchd integration for macOS to run FlowPilot as a system service.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir

# launchd plist configuration
PLIST_NAME = "com.flowpilot.server"
PLIST_FILENAME = f"{PLIST_NAME}.plist"


def get_plist_path() -> Path:
    """Get the path to the launchd plist file.

    Returns:
        Path to ~/Library/LaunchAgents/com.flowpilot.server.plist
    """
    return Path.home() / "Library" / "LaunchAgents" / PLIST_FILENAME


def get_python_path() -> str:
    """Get the path to the Python interpreter.

    Returns:
        Path to the Python executable.
    """
    return sys.executable


def get_flowpilot_command() -> str:
    """Get the path to the flowpilot command.

    Returns:
        Path to the flowpilot CLI.
    """
    # Check if flowpilot is installed as a command
    result = subprocess.run(
        ["which", "flowpilot"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()

    # Fall back to running as a module
    return f"{get_python_path()} -m flowpilot.cli"


def generate_plist(host: str, port: int, env_vars: dict[str, str] | None = None) -> str:
    """Generate the launchd plist content.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        env_vars: Additional environment variables.

    Returns:
        plist XML content.
    """
    flowpilot_dir = get_flowpilot_dir()
    log_dir = flowpilot_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    stdout_log = log_dir / "server.log"
    stderr_log = log_dir / "server.error.log"

    # Build environment variables section
    env_section = ""
    if env_vars:
        env_items = "\n".join(
            f"            <key>{key}</key>\n            <string>{value}</string>"
            for key, value in env_vars.items()
        )
        env_section = f"""
        <key>EnvironmentVariables</key>
        <dict>
{env_items}
        </dict>"""

    # Get the flowpilot command
    python_path = get_python_path()

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>flowpilot.cli</string>
        <string>serve</string>
        <string>--host</string>
        <string>{host}</string>
        <string>--port</string>
        <string>{port!s}</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>WorkingDirectory</key>
    <string>{flowpilot_dir}</string>

    <key>StandardOutPath</key>
    <string>{stdout_log}</string>

    <key>StandardErrorPath</key>
    <string>{stderr_log}</string>{env_section}
</dict>
</plist>
"""
    return plist


def is_service_installed() -> bool:
    """Check if the launchd service is installed.

    Returns:
        True if the plist file exists.
    """
    return get_plist_path().exists()


def is_service_loaded() -> bool:
    """Check if the launchd service is loaded.

    Returns:
        True if the service is loaded.
    """
    result = subprocess.run(
        ["launchctl", "list", PLIST_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def load_service() -> bool:
    """Load the launchd service.

    Returns:
        True if successful.
    """
    plist_path = get_plist_path()
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def unload_service() -> bool:
    """Unload the launchd service.

    Returns:
        True if successful.
    """
    plist_path = get_plist_path()
    result = subprocess.run(
        ["launchctl", "unload", str(plist_path)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@app.command("install-service")
def install_service(
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
    start: bool = typer.Option(
        True,
        "--start/--no-start",
        help="Start service after installation",
    ),
) -> None:
    """Install FlowPilot as a macOS launchd service.

    Creates a launchd plist file in ~/Library/LaunchAgents that will
    automatically start the FlowPilot server on login.

    Examples:
        flowpilot install-service
        flowpilot install-service --port 9000
        flowpilot install-service --no-start
    """
    # Check if already installed
    if is_service_installed():
        console.print("[yellow]Service is already installed.[/]")
        console.print(f"Plist file: {get_plist_path()}")
        console.print()
        console.print("To reinstall, first run [cyan]flowpilot uninstall-service[/]")
        raise typer.Exit(1)

    # Ensure FlowPilot is initialized
    flowpilot_dir = get_flowpilot_dir()
    if not flowpilot_dir.exists():
        console.print("[yellow]FlowPilot not initialized.[/]")
        console.print("Run [cyan]flowpilot init[/] first.")
        raise typer.Exit(1)

    # Generate plist
    plist_content = generate_plist(host, port)
    plist_path = get_plist_path()

    # Ensure LaunchAgents directory exists
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    # Write plist file
    plist_path.write_text(plist_content)

    console.print("[green]Service installed successfully![/]")
    console.print(f"[dim]Plist file: {plist_path}[/]")
    console.print()

    if start:
        console.print("Loading service...")
        if load_service():
            console.print("[green]Service started![/]")
            console.print(f"Server running on http://{host}:{port}")
        else:
            console.print("[yellow]Failed to start service.[/]")
            console.print("Try manually: [cyan]launchctl load {plist_path}[/]")
    else:
        console.print("To start the service, run:")
        console.print(f"  [cyan]launchctl load {plist_path}[/]")

    console.print()
    console.print("[dim]The service will automatically start on login.[/]")


@app.command("uninstall-service")
def uninstall_service() -> None:
    """Remove the FlowPilot launchd service.

    Stops the service if running and removes the plist file.

    Examples:
        flowpilot uninstall-service
    """
    if not is_service_installed():
        console.print("[yellow]Service is not installed.[/]")
        raise typer.Exit(0)

    plist_path = get_plist_path()

    # Unload if loaded
    if is_service_loaded():
        console.print("Stopping service...")
        if unload_service():
            console.print("[green]Service stopped.[/]")
        else:
            console.print("[yellow]Warning: Could not unload service.[/]")

    # Remove plist file
    try:
        plist_path.unlink()
        console.print("[green]Service uninstalled successfully![/]")
        console.print(f"[dim]Removed: {plist_path}[/]")
    except OSError as e:
        console.print(f"[red]Error removing plist file: {e}[/]")
        raise typer.Exit(1)


@app.command("service-status")
def service_status() -> None:
    """Check the status of the FlowPilot launchd service.

    Examples:
        flowpilot service-status
    """
    plist_path = get_plist_path()

    console.print("[bold]FlowPilot Service Status[/]")
    console.print()

    if not is_service_installed():
        console.print("[dim]Installed:[/] [yellow]No[/]")
        console.print()
        console.print("To install, run [cyan]flowpilot install-service[/]")
        return

    console.print("[dim]Installed:[/] [green]Yes[/]")
    console.print(f"[dim]Plist:[/] {plist_path}")

    if is_service_loaded():
        console.print("[dim]Loaded:[/] [green]Yes[/]")

        # Try to get more info
        result = subprocess.run(
            ["launchctl", "list", PLIST_NAME],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Parse output for PID
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split("\t")
                if len(parts) >= 1 and parts[0] != "-":
                    console.print(f"[dim]PID:[/] {parts[0]}")
    else:
        console.print("[dim]Loaded:[/] [yellow]No[/]")
        console.print()
        console.print("To load, run:")
        console.print(f"  [cyan]launchctl load {plist_path}[/]")

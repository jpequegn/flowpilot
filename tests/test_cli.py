"""Tests for FlowPilot CLI."""

from typer.testing import CliRunner

from flowpilot import __version__
from flowpilot.cli import app

runner = CliRunner()


def test_version_command() -> None:
    """Test version command shows version."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_shows_commands() -> None:
    """Test help shows available commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "run" in result.stdout
    assert "list" in result.stdout
    assert "validate" in result.stdout


def test_init_command_exists() -> None:
    """Test init command is available."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.stdout


def test_run_requires_name() -> None:
    """Test run command requires workflow name."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
    # Typer outputs errors to stderr, which is captured in output
    assert "Missing argument" in result.output or result.exit_code == 2


def test_validate_requires_name() -> None:
    """Test validate command requires workflow name."""
    result = runner.invoke(app, ["validate"])
    assert result.exit_code != 0
    # Typer outputs errors to stderr, which is captured in output
    assert "Missing argument" in result.output or result.exit_code == 2

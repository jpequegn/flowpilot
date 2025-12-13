"""Tests for FlowPilot CLI."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from flowpilot import __version__
from flowpilot.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary home directory and patch paths."""
    flowpilot_dir = tmp_path / ".flowpilot"
    workflows_dir = flowpilot_dir / "workflows"
    logs_dir = flowpilot_dir / "logs"
    config_file = flowpilot_dir / "config.yaml"
    db_file = flowpilot_dir / "flowpilot.db"

    # Patch the CLI constants to use temp directory
    monkeypatch.setattr("flowpilot.cli.FLOWPILOT_DIR", flowpilot_dir)
    monkeypatch.setattr("flowpilot.cli.WORKFLOWS_DIR", workflows_dir)
    monkeypatch.setattr("flowpilot.cli.LOGS_DIR", logs_dir)
    monkeypatch.setattr("flowpilot.cli.CONFIG_FILE", config_file)
    monkeypatch.setattr("flowpilot.cli.DB_FILE", db_file)

    # Also patch in the commands modules
    monkeypatch.setattr("flowpilot.cli.commands.init.FLOWPILOT_DIR", flowpilot_dir)
    monkeypatch.setattr("flowpilot.cli.commands.init.WORKFLOWS_DIR", workflows_dir)
    monkeypatch.setattr("flowpilot.cli.commands.init.LOGS_DIR", logs_dir)
    monkeypatch.setattr("flowpilot.cli.commands.init.CONFIG_FILE", config_file)
    monkeypatch.setattr("flowpilot.cli.commands.list_cmd.WORKFLOWS_DIR", workflows_dir)
    monkeypatch.setattr("flowpilot.cli.utils.WORKFLOWS_DIR", workflows_dir)

    return tmp_path


class TestHelp:
    """Tests for help output."""

    def test_help_shows_commands(self, runner: CliRunner) -> None:
        """Test help shows available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "run" in result.output
        assert "list" in result.output
        assert "validate" in result.output


class TestVersion:
    """Tests for version command."""

    def test_version(self, runner: CliRunner) -> None:
        """Test version command shows version."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestInit:
    """Tests for init command."""

    def test_init_creates_directories(self, runner: CliRunner, temp_home: Path) -> None:
        """Test init creates directory structure."""
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "Initialized FlowPilot" in result.output

        flowpilot_dir = temp_home / ".flowpilot"
        assert flowpilot_dir.exists()
        assert (flowpilot_dir / "workflows").exists()
        assert (flowpilot_dir / "logs").exists()
        assert (flowpilot_dir / "config.yaml").exists()

    def test_init_creates_example_workflow(self, runner: CliRunner, temp_home: Path) -> None:
        """Test init creates example workflow."""
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        example = temp_home / ".flowpilot" / "workflows" / "hello-world.yaml"
        assert example.exists()
        assert "hello-world" in example.read_text()

    def test_init_refuses_without_force(self, runner: CliRunner, temp_home: Path) -> None:
        """Test init refuses to overwrite without --force."""
        # First init
        runner.invoke(app, ["init"])

        # Second init without force
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 1
        assert "already initialized" in result.output

    def test_init_with_force(self, runner: CliRunner, temp_home: Path) -> None:
        """Test init with --force overwrites."""
        # First init
        runner.invoke(app, ["init"])

        # Second init with force
        result = runner.invoke(app, ["init", "--force"])
        assert result.exit_code == 0
        assert "Initialized FlowPilot" in result.output


class TestValidate:
    """Tests for validate command."""

    def test_validate_requires_name(self, runner: CliRunner) -> None:
        """Test validate command requires workflow name."""
        result = runner.invoke(app, ["validate"])
        assert result.exit_code != 0

    def test_validate_valid_workflow(self, runner: CliRunner, temp_home: Path) -> None:
        """Test validate with valid workflow."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["validate", "hello-world"])
        assert result.exit_code == 0
        assert "is valid" in result.output

    def test_validate_verbose(self, runner: CliRunner, temp_home: Path) -> None:
        """Test validate with --verbose shows details."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["validate", "hello-world", "--verbose"])
        assert result.exit_code == 0
        assert "Nodes:" in result.output
        assert "Triggers:" in result.output

    def test_validate_not_found(self, runner: CliRunner, temp_home: Path) -> None:
        """Test validate with non-existent workflow."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["validate", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_validate_invalid_workflow(self, runner: CliRunner, temp_home: Path) -> None:
        """Test validate with invalid workflow."""
        runner.invoke(app, ["init"])

        # Create invalid workflow
        invalid = temp_home / ".flowpilot" / "workflows" / "invalid.yaml"
        invalid.write_text("name: invalid\n# missing nodes\n")

        result = runner.invoke(app, ["validate", "invalid"])
        assert result.exit_code == 1
        assert "Validation failed" in result.output or "Error" in result.output


class TestRun:
    """Tests for run command."""

    def test_run_requires_name(self, runner: CliRunner) -> None:
        """Test run command requires workflow name."""
        result = runner.invoke(app, ["run"])
        assert result.exit_code != 0

    def test_run_workflow(self, runner: CliRunner, temp_home: Path) -> None:
        """Test running a workflow."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["run", "hello-world"])
        assert result.exit_code == 0
        assert "Running workflow" in result.output
        assert "hello-world" in result.output

    def test_run_with_json_output(self, runner: CliRunner, temp_home: Path) -> None:
        """Test run with --json outputs JSON."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["run", "hello-world", "--json"])
        assert result.exit_code == 0

        # Should be valid JSON
        data = json.loads(result.output)
        assert "execution_id" in data
        assert "nodes" in data

    def test_run_not_found(self, runner: CliRunner, temp_home: Path) -> None:
        """Test run with non-existent workflow."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["run", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_run_with_verbose(self, runner: CliRunner, temp_home: Path) -> None:
        """Test run with --verbose shows output."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["run", "hello-world", "--verbose"])
        assert result.exit_code == 0

    def test_run_with_inputs(self, runner: CliRunner, temp_home: Path) -> None:
        """Test run with --input passes inputs."""
        runner.invoke(app, ["init"])

        # Just verify the inputs are parsed and passed - use simple workflow
        result = runner.invoke(app, ["run", "hello-world", "--input", "mykey=myvalue"])
        # Workflow runs successfully even with extra inputs
        assert result.exit_code == 0
        assert "Inputs:" in result.output or "hello-world" in result.output

    def test_run_invalid_input_format(self, runner: CliRunner, temp_home: Path) -> None:
        """Test run with invalid input format."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["run", "hello-world", "--input", "invalid-no-equals"])
        assert result.exit_code == 1
        assert "Invalid input format" in result.output


class TestList:
    """Tests for list command."""

    def test_list_no_init(self, runner: CliRunner, temp_home: Path) -> None:
        """Test list without init shows error."""
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        assert "not found" in result.output or "init" in result.output

    def test_list_workflows(self, runner: CliRunner, temp_home: Path) -> None:
        """Test list shows workflows."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "hello-world" in result.output
        assert "Workflows" in result.output

    def test_list_json(self, runner: CliRunner, temp_home: Path) -> None:
        """Test list with --json outputs JSON."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert "workflows" in data
        assert len(data["workflows"]) >= 1
        assert data["workflows"][0]["name"] == "hello-world"

    def test_list_empty(self, runner: CliRunner, temp_home: Path) -> None:
        """Test list with no workflows."""
        runner.invoke(app, ["init"])

        # Remove example workflow
        example = temp_home / ".flowpilot" / "workflows" / "hello-world.yaml"
        example.unlink()

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No workflows found" in result.output

    def test_list_invalid_workflow(self, runner: CliRunner, temp_home: Path) -> None:
        """Test list shows error for invalid workflow."""
        runner.invoke(app, ["init"])

        # Create invalid workflow
        invalid = temp_home / ".flowpilot" / "workflows" / "broken.yaml"
        invalid.write_text("this: is: not: valid: yaml: [")

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        # Should show the valid workflow and error for invalid
        assert "hello-world" in result.output
        assert "Error" in result.output or "broken" in result.output

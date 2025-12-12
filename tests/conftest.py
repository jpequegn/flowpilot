"""Pytest configuration and shared fixtures."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def flowpilot_home(temp_dir: Path) -> Path:
    """Create a temporary FlowPilot home directory."""
    home = temp_dir / ".flowpilot"
    home.mkdir()
    (home / "workflows").mkdir()
    return home

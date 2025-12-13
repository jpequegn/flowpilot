"""Tests for file read and write node executors."""

import os
from pathlib import Path

import pytest

from flowpilot.engine import ExecutionContext
from flowpilot.engine.nodes import FileReadExecutor, FileWriteExecutor
from flowpilot.models import FileReadNode, FileWriteNode


@pytest.fixture
def read_executor() -> FileReadExecutor:
    """Create a file read executor instance."""
    return FileReadExecutor()


@pytest.fixture
def write_executor() -> FileWriteExecutor:
    """Create a file write executor instance."""
    return FileWriteExecutor()


@pytest.fixture
def context() -> ExecutionContext:
    """Create an execution context."""
    return ExecutionContext(workflow_name="test")


class TestFileReadExecutor:
    """Tests for FileReadExecutor."""

    @pytest.mark.asyncio
    async def test_read_simple_file(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test reading a simple text file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        node = FileReadNode(
            type="file-read",
            id="read-test",
            path=str(test_file),
        )
        result = await read_executor.execute(node, context)

        assert result.status == "success"
        assert result.output == "Hello, World!"
        assert result.data["path"] == str(test_file)
        assert result.data["size"] == 13
        assert result.data["lines"] == 1
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_read_multiline_file(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test reading a multiline file."""
        test_file = tmp_path / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3\nLine 4"
        test_file.write_text(content)

        node = FileReadNode(
            type="file-read",
            id="multiline-read",
            path=str(test_file),
        )
        result = await read_executor.execute(node, context)

        assert result.status == "success"
        assert result.output == content
        assert result.data["lines"] == 4

    @pytest.mark.asyncio
    async def test_read_empty_file(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test reading an empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        node = FileReadNode(
            type="file-read",
            id="empty-read",
            path=str(test_file),
        )
        result = await read_executor.execute(node, context)

        assert result.status == "success"
        assert result.output == ""
        assert result.data["size"] == 0
        assert result.data["lines"] == 0

    @pytest.mark.asyncio
    async def test_read_file_not_found(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test reading a non-existent file."""
        node = FileReadNode(
            type="file-read",
            id="not-found-read",
            path=str(tmp_path / "nonexistent.txt"),
        )
        result = await read_executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_read_with_custom_encoding(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test reading a file with custom encoding."""
        test_file = tmp_path / "latin1.txt"
        content = "Héllo Wörld"
        test_file.write_text(content, encoding="latin-1")

        node = FileReadNode(
            type="file-read",
            id="encoding-read",
            path=str(test_file),
            encoding="latin-1",
        )
        result = await read_executor.execute(node, context)

        assert result.status == "success"
        assert result.output == content

    @pytest.mark.asyncio
    async def test_read_encoding_error(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test reading a file with wrong encoding."""
        test_file = tmp_path / "binary.txt"
        # Write some bytes that aren't valid UTF-8
        test_file.write_bytes(b"\xff\xfe\x00\x01")

        node = FileReadNode(
            type="file-read",
            id="encoding-error-read",
            path=str(test_file),
            encoding="utf-8",
        )
        result = await read_executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "encoding" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_read_path_expansion_tilde(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
    ) -> None:
        """Test ~ expansion in file path."""
        # We can't easily test this without creating files in home dir
        # So we just test that the path gets expanded
        node = FileReadNode(
            type="file-read",
            id="tilde-read",
            path="~/nonexistent_test_file_12345.txt",
        )
        result = await read_executor.execute(node, context)

        # Should fail with file not found (not path error)
        assert result.status == "error"
        assert "not found" in result.error_message.lower()
        # The error message should contain expanded path, not ~
        assert "~" not in result.error_message or os.path.expanduser("~") in result.error_message

    @pytest.mark.asyncio
    async def test_read_path_expansion_env_var(
        self,
        read_executor: FileReadExecutor,
        context: ExecutionContext,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test environment variable expansion in file path."""
        test_file = tmp_path / "env_test.txt"
        test_file.write_text("env content")

        monkeypatch.setenv("TEST_DIR", str(tmp_path))

        node = FileReadNode(
            type="file-read",
            id="env-read",
            path="$TEST_DIR/env_test.txt",
        )
        result = await read_executor.execute(node, context)

        assert result.status == "success"
        assert result.output == "env content"


class TestFileWriteExecutor:
    """Tests for FileWriteExecutor."""

    @pytest.mark.asyncio
    async def test_write_simple_file(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test writing a simple text file."""
        test_file = tmp_path / "output.txt"

        node = FileWriteNode(
            type="file-write",
            id="write-test",
            path=str(test_file),
            content="Hello, FlowPilot!",
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert result.output == str(test_file)
        assert result.data["path"] == str(test_file)
        assert result.data["mode"] == "write"
        assert test_file.read_text() == "Hello, FlowPilot!"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_write_creates_parent_directories(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test that parent directories are created."""
        test_file = tmp_path / "nested" / "deep" / "output.txt"

        node = FileWriteNode(
            type="file-write",
            id="nested-write",
            path=str(test_file),
            content="Nested content",
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert test_file.exists()
        assert test_file.read_text() == "Nested content"

    @pytest.mark.asyncio
    async def test_write_overwrites_existing(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test that existing file is overwritten in write mode."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Original content")

        node = FileWriteNode(
            type="file-write",
            id="overwrite-test",
            path=str(test_file),
            content="New content",
            mode="write",
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert test_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_write_append_mode(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test appending to existing file."""
        test_file = tmp_path / "append.txt"
        test_file.write_text("Original")

        node = FileWriteNode(
            type="file-write",
            id="append-test",
            path=str(test_file),
            content=" appended",
            mode="append",
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert result.data["mode"] == "append"
        assert test_file.read_text() == "Original appended"

    @pytest.mark.asyncio
    async def test_write_append_creates_new_file(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test append mode creates file if it doesn't exist."""
        test_file = tmp_path / "new_append.txt"

        node = FileWriteNode(
            type="file-write",
            id="new-append-test",
            path=str(test_file),
            content="First content",
            mode="append",
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert test_file.read_text() == "First content"

    @pytest.mark.asyncio
    async def test_write_with_custom_encoding(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test writing with custom encoding."""
        test_file = tmp_path / "latin1.txt"

        node = FileWriteNode(
            type="file-write",
            id="encoding-write",
            path=str(test_file),
            content="Héllo Wörld",
            encoding="latin-1",
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert test_file.read_text(encoding="latin-1") == "Héllo Wörld"

    @pytest.mark.asyncio
    async def test_write_multiline_content(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test writing multiline content."""
        test_file = tmp_path / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3"

        node = FileWriteNode(
            type="file-write",
            id="multiline-write",
            path=str(test_file),
            content=content,
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert test_file.read_text() == content

    @pytest.mark.asyncio
    async def test_write_reports_size(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
    ) -> None:
        """Test that file size is reported."""
        test_file = tmp_path / "sized.txt"
        content = "12345678901234567890"  # 20 bytes

        node = FileWriteNode(
            type="file-write",
            id="size-test",
            path=str(test_file),
            content=content,
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert result.data["size"] == 20

    @pytest.mark.asyncio
    async def test_write_path_expansion_env_var(
        self,
        write_executor: FileWriteExecutor,
        context: ExecutionContext,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test environment variable expansion in file path."""
        monkeypatch.setenv("TEST_OUTPUT_DIR", str(tmp_path))

        node = FileWriteNode(
            type="file-write",
            id="env-write",
            path="$TEST_OUTPUT_DIR/env_output.txt",
            content="env content",
        )
        result = await write_executor.execute(node, context)

        assert result.status == "success"
        assert (tmp_path / "env_output.txt").read_text() == "env content"

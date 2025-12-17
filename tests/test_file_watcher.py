"""Tests for file watcher service."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from watchdog.events import FileCreatedEvent, FileModifiedEvent

from flowpilot.models.triggers import FileWatchTrigger
from flowpilot.scheduler.file_watcher import (
    DebouncedHandler,
    FileWatchService,
    set_global_file_watcher_runner,
)


class TestDebouncedHandler:
    """Tests for DebouncedHandler class."""

    def test_init(self) -> None:
        """Test handler initialization."""
        callback = MagicMock()
        handler = DebouncedHandler(
            callback=callback,
            events=["created", "modified"],
            pattern="*.txt",
            debounce_seconds=0.5,
        )

        assert handler.callback == callback
        assert handler.events == ["created", "modified"]
        assert handler.pattern == "*.txt"
        assert handler.debounce_seconds == 0.5

    def test_should_handle_directory_event(self) -> None:
        """Test that directory events are ignored."""
        from watchdog.events import DirCreatedEvent

        callback = MagicMock()
        handler = DebouncedHandler(
            callback=callback,
            events=["created"],
        )

        event = DirCreatedEvent("/tmp/somedir")
        assert handler._should_handle(event) is False

    def test_should_handle_event_type_filter(self) -> None:
        """Test event type filtering."""
        callback = MagicMock()
        handler = DebouncedHandler(
            callback=callback,
            events=["created"],  # Only handle created events
        )

        created_event = FileCreatedEvent("/tmp/file.txt")
        assert handler._should_handle(created_event) is True

        modified_event = FileModifiedEvent("/tmp/file.txt")
        assert handler._should_handle(modified_event) is False

    def test_should_handle_pattern_filter(self) -> None:
        """Test glob pattern filtering."""
        callback = MagicMock()
        handler = DebouncedHandler(
            callback=callback,
            events=["created"],
            pattern="*.txt",
        )

        txt_event = FileCreatedEvent("/tmp/file.txt")
        assert handler._should_handle(txt_event) is True

        json_event = FileCreatedEvent("/tmp/file.json")
        assert handler._should_handle(json_event) is False

    def test_should_handle_no_pattern(self) -> None:
        """Test that no pattern matches all files."""
        callback = MagicMock()
        handler = DebouncedHandler(
            callback=callback,
            events=["created"],
            pattern=None,
        )

        txt_event = FileCreatedEvent("/tmp/file.txt")
        assert handler._should_handle(txt_event) is True

        any_event = FileCreatedEvent("/tmp/any.whatever")
        assert handler._should_handle(any_event) is True

    def test_debounce_callback(self) -> None:
        """Test that callbacks are debounced."""
        callback = MagicMock()
        handler = DebouncedHandler(
            callback=callback,
            events=["modified"],
            debounce_seconds=0.1,
        )

        event = FileModifiedEvent("/tmp/file.txt")

        # Trigger multiple events rapidly
        handler.on_any_event(event)
        handler.on_any_event(event)
        handler.on_any_event(event)

        # Wait for debounce (use longer timeout for CI reliability)
        time.sleep(0.5)

        # Should only be called once due to debouncing
        assert callback.call_count == 1

    def test_cancel_all(self) -> None:
        """Test canceling all pending callbacks."""
        callback = MagicMock()
        handler = DebouncedHandler(
            callback=callback,
            events=["modified"],
            debounce_seconds=1.0,  # Long debounce
        )

        event = FileModifiedEvent("/tmp/file.txt")
        handler.on_any_event(event)

        # Cancel before debounce completes
        handler.cancel_all()

        # Wait a bit
        time.sleep(0.1)

        # Callback should not have been called
        assert callback.call_count == 0


class TestFileWatchService:
    """Tests for FileWatchService class."""

    def test_init(self) -> None:
        """Test service initialization."""
        service = FileWatchService()

        assert service.is_running is False
        assert len(service._watches) == 0
        assert len(service._handlers) == 0

    def test_start_stop(self) -> None:
        """Test starting and stopping the service."""
        service = FileWatchService()

        service.start()
        assert service.is_running is True

        service.stop()
        assert service.is_running is False

    def test_start_idempotent(self) -> None:
        """Test that start is idempotent."""
        service = FileWatchService()

        service.start()
        service.start()  # Should not raise
        assert service.is_running is True

        service.stop()

    def test_stop_idempotent(self) -> None:
        """Test that stop is idempotent."""
        service = FileWatchService()

        service.stop()  # Should not raise
        assert service.is_running is False

    def test_add_watch(self, tmp_path: Path) -> None:
        """Test adding a file watch."""
        service = FileWatchService()
        service.start()

        try:
            trigger = FileWatchTrigger(
                type="file-watch",
                path=str(tmp_path),
                events=["created"],
                pattern="*.txt",
            )

            watch_id = service.add_watch(
                "test-workflow",
                trigger,
                "/path/to/workflow.yaml",
            )

            assert watch_id == "file-watch:test-workflow"
            assert "test-workflow" in service._watches
            assert "test-workflow" in service._handlers

        finally:
            service.stop()

    def test_remove_watch(self, tmp_path: Path) -> None:
        """Test removing a file watch."""
        service = FileWatchService()
        service.start()

        try:
            trigger = FileWatchTrigger(
                type="file-watch",
                path=str(tmp_path),
                events=["created"],
            )

            service.add_watch("test-workflow", trigger, "/path/to/workflow.yaml")
            assert "test-workflow" in service._watches

            result = service.remove_watch("test-workflow")
            assert result is True
            assert "test-workflow" not in service._watches
            assert "test-workflow" not in service._handlers

        finally:
            service.stop()

    def test_remove_nonexistent_watch(self) -> None:
        """Test removing a non-existent watch returns False."""
        service = FileWatchService()
        service.start()

        try:
            result = service.remove_watch("nonexistent")
            assert result is False

        finally:
            service.stop()

    def test_get_watches(self, tmp_path: Path) -> None:
        """Test getting all watches."""
        service = FileWatchService()
        service.start()

        try:
            trigger = FileWatchTrigger(
                type="file-watch",
                path=str(tmp_path),
                events=["created"],
            )

            service.add_watch("workflow-1", trigger, "/path/to/workflow1.yaml")
            service.add_watch("workflow-2", trigger, "/path/to/workflow2.yaml")

            watches = service.get_watches()
            assert len(watches) == 2

            workflow_names = [w["workflow"] for w in watches]
            assert "workflow-1" in workflow_names
            assert "workflow-2" in workflow_names

        finally:
            service.stop()

    def test_get_watch(self, tmp_path: Path) -> None:
        """Test getting a specific watch."""
        service = FileWatchService()
        service.start()

        try:
            trigger = FileWatchTrigger(
                type="file-watch",
                path=str(tmp_path),
                events=["created"],
            )

            service.add_watch("test-workflow", trigger, "/path/to/workflow.yaml")

            watch = service.get_watch("test-workflow")
            assert watch is not None
            assert watch["workflow"] == "test-workflow"
            assert watch["path"] == str(tmp_path)

        finally:
            service.stop()

    def test_get_watch_nonexistent(self) -> None:
        """Test getting a non-existent watch returns None."""
        service = FileWatchService()

        watch = service.get_watch("nonexistent")
        assert watch is None

    def test_add_watch_replaces_existing(self, tmp_path: Path) -> None:
        """Test that adding a watch replaces existing watch."""
        service = FileWatchService()
        service.start()

        try:
            trigger1 = FileWatchTrigger(
                type="file-watch",
                path=str(tmp_path),
                events=["created"],
            )

            trigger2 = FileWatchTrigger(
                type="file-watch",
                path=str(tmp_path),
                events=["modified"],
            )

            service.add_watch("test-workflow", trigger1, "/path/to/workflow.yaml")
            service.add_watch("test-workflow", trigger2, "/path/to/workflow.yaml")

            # Should only have one watch
            watches = service.get_watches()
            assert len(watches) == 1

        finally:
            service.stop()

    def test_path_expansion(self, tmp_path: Path) -> None:
        """Test that ~ in paths is expanded."""
        service = FileWatchService()
        service.start()

        try:
            # Create a trigger with ~ in path
            trigger = FileWatchTrigger(
                type="file-watch",
                path="~/Downloads",
                events=["created"],
            )

            # Mock the observer schedule to capture the path
            with patch.object(service._observer, "schedule") as mock_schedule:
                mock_schedule.return_value = MagicMock()

                service.add_watch("test-workflow", trigger, "/path/to/workflow.yaml")

                # Verify that the path was expanded
                call_args = mock_schedule.call_args
                watched_path = call_args[0][1]
                assert "~" not in watched_path
                assert watched_path == str(Path.home() / "Downloads")

        finally:
            service.stop()


class TestSetGlobalRunner:
    """Tests for set_global_file_watcher_runner function."""

    def test_set_runner(self) -> None:
        """Test setting the global runner."""
        mock_runner = MagicMock()
        set_global_file_watcher_runner(mock_runner)

        # Import the module variable to check
        from flowpilot.scheduler import file_watcher

        assert file_watcher._global_runner == mock_runner

        # Clean up
        set_global_file_watcher_runner(None)
        assert file_watcher._global_runner is None


class TestFileWatchIntegration:
    """Integration tests for file watching."""

    def test_file_created_event(self, tmp_path: Path) -> None:
        """Test that file creation triggers callback."""
        callback_event = threading.Event()
        captured_events: list = []

        def callback(event):
            captured_events.append(event)
            callback_event.set()

        handler = DebouncedHandler(
            callback=callback,
            events=["created"],
            debounce_seconds=0.05,
        )

        service = FileWatchService()
        service._observer.schedule(handler, str(tmp_path), recursive=True)
        service.start()

        try:
            # Create a file
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello")

            # Wait for callback
            callback_event.wait(timeout=2.0)

            assert len(captured_events) >= 1
            assert any(e.src_path.endswith("test.txt") for e in captured_events)

        finally:
            service.stop()

    def test_file_modified_event(self, tmp_path: Path) -> None:
        """Test that file modification triggers callback."""
        callback_event = threading.Event()
        captured_events: list = []

        def callback(event):
            captured_events.append(event)
            callback_event.set()

        handler = DebouncedHandler(
            callback=callback,
            events=["modified"],
            debounce_seconds=0.05,
        )

        # Create file first
        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")

        service = FileWatchService()
        service._observer.schedule(handler, str(tmp_path), recursive=True)
        service.start()

        try:
            # Small delay to ensure watcher is ready
            time.sleep(0.1)

            # Modify the file
            test_file.write_text("modified")

            # Wait for callback
            callback_event.wait(timeout=2.0)

            assert len(captured_events) >= 1

        finally:
            service.stop()

    def test_pattern_filtering_integration(self, tmp_path: Path) -> None:
        """Test pattern filtering with real file events."""
        callback_event = threading.Event()
        captured_events: list = []

        def callback(event):
            captured_events.append(event)
            callback_event.set()

        handler = DebouncedHandler(
            callback=callback,
            events=["created"],
            pattern="*.txt",
            debounce_seconds=0.05,
        )

        service = FileWatchService()
        service._observer.schedule(handler, str(tmp_path), recursive=True)
        service.start()

        try:
            # Create a .json file (should be ignored)
            json_file = tmp_path / "test.json"
            json_file.write_text("{}")

            time.sleep(0.1)

            # Create a .txt file (should trigger)
            txt_file = tmp_path / "test.txt"
            txt_file.write_text("hello")

            # Wait for callback
            callback_event.wait(timeout=2.0)

            # Should only have txt events
            txt_events = [e for e in captured_events if e.src_path.endswith(".txt")]
            json_events = [e for e in captured_events if e.src_path.endswith(".json")]

            assert len(txt_events) >= 1
            assert len(json_events) == 0

        finally:
            service.stop()

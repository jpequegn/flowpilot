"""File system watching service for FlowPilot workflows."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from flowpilot.engine.runner import WorkflowRunner
    from flowpilot.models.triggers import FileWatchTrigger

logger = logging.getLogger(__name__)

# Global reference to runner for file watch execution (set via set_global_runner)
_global_runner: WorkflowRunner | None = None


def set_global_file_watcher_runner(runner: WorkflowRunner | None) -> None:
    """Set the global workflow runner for file watch execution.

    Args:
        runner: WorkflowRunner instance to use for executing workflows.
    """
    global _global_runner
    _global_runner = runner


class DebouncedHandler(FileSystemEventHandler):
    """Handler that debounces rapid file changes.

    Filters events by type and glob pattern, and debounces rapid changes
    to avoid triggering multiple workflow executions for a single file operation.
    """

    def __init__(
        self,
        callback: Any,  # Callable[[FileSystemEvent], None]
        events: Sequence[str],
        pattern: str | None = None,
        debounce_seconds: float = 1.0,
    ) -> None:
        """Initialize the debounced handler.

        Args:
            callback: Function to call when debounced event fires.
            events: List of event types to handle (created, modified, deleted).
            pattern: Optional glob pattern to filter files.
            debounce_seconds: Time to wait before firing callback.
        """
        super().__init__()
        self.callback = callback
        self.events = events
        self.pattern = pattern
        self.debounce_seconds = debounce_seconds
        self._pending: dict[str, datetime] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _should_handle(self, event: FileSystemEvent) -> bool:
        """Check if event should be handled.

        Args:
            event: The file system event to check.

        Returns:
            True if event should be handled, False otherwise.
        """
        if event.is_directory:
            return False

        # Map watchdog event types to our types
        event_type_map = {
            "created": "created",
            "modified": "modified",
            "deleted": "deleted",
            "moved": "modified",  # Treat move as modified
        }

        event_type = event_type_map.get(event.event_type)
        if event_type not in self.events:
            return False

        # Check pattern
        if self.pattern:
            src_path = event.src_path
            path_str = src_path if isinstance(src_path, str) else src_path.decode()
            filename = Path(path_str).name
            if not fnmatch.fnmatch(filename, self.pattern):
                return False

        return True

    def _debounced_callback(self, event: FileSystemEvent) -> None:
        """Called after debounce period.

        Args:
            event: The file system event to handle.
        """
        src_path = event.src_path
        path = src_path if isinstance(src_path, str) else src_path.decode()
        with self._lock:
            if path in self._pending:
                del self._pending[path]
            if path in self._timers:
                del self._timers[path]

        logger.debug(f"Debounce complete for {path}, calling callback")
        self.callback(event)

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event.

        Args:
            event: The file system event.
        """
        if not self._should_handle(event):
            return

        src_path = event.src_path
        path = src_path if isinstance(src_path, str) else src_path.decode()
        logger.debug(f"File event: {event.event_type} - {path}")

        with self._lock:
            # Cancel existing timer for this path
            if path in self._timers:
                self._timers[path].cancel()

            # Record pending event
            self._pending[path] = datetime.now()

            # Schedule new callback after debounce period
            timer = threading.Timer(
                self.debounce_seconds,
                self._debounced_callback,
                args=[event],
            )
            self._timers[path] = timer
            timer.start()

    def cancel_all(self) -> None:
        """Cancel all pending timers."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            self._pending.clear()


class FileWatchService:
    """Manages file system watchers for workflows.

    Provides functionality to add, remove, and manage file watches
    that trigger workflow executions when file events occur.
    """

    def __init__(self) -> None:
        """Initialize the file watch service."""
        self._observer = Observer()
        self._watches: dict[str, Any] = {}  # workflow_name -> watch handle
        self._handlers: dict[str, DebouncedHandler] = {}  # workflow_name -> handler
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if file watcher is running."""
        return self._running

    def start(self) -> None:
        """Start the file watcher observer."""
        if self._running:
            return

        self._observer.start()
        self._running = True
        logger.info("File watcher started")

    def stop(self) -> None:
        """Stop all file watchers."""
        if not self._running:
            return

        # Cancel all pending debounced callbacks
        for handler in self._handlers.values():
            handler.cancel_all()

        self._observer.stop()
        self._observer.join(timeout=5.0)
        self._running = False
        logger.info("File watcher stopped")

    def add_watch(
        self,
        workflow_name: str,
        trigger: FileWatchTrigger,
        workflow_path: str,
        debounce_seconds: float = 1.0,
    ) -> str:
        """Add a file watch for a workflow.

        Args:
            workflow_name: Name of the workflow.
            trigger: File watch trigger configuration.
            workflow_path: Path to the workflow file.
            debounce_seconds: Debounce delay in seconds.

        Returns:
            Watch identifier.
        """
        # Remove existing watch if any
        self.remove_watch(workflow_name)

        watch_path = Path(trigger.path).expanduser().resolve()

        def on_file_event(event: FileSystemEvent) -> None:
            """Callback when file event occurs."""
            src_path = event.src_path
            event_path = src_path if isinstance(src_path, str) else src_path.decode()
            _execute_file_watch_workflow(
                workflow_name=workflow_name,
                workflow_path=workflow_path,
                event_type=event.event_type,
                event_path=event_path,
                event_is_directory=event.is_directory,
            )

        handler = DebouncedHandler(
            callback=on_file_event,
            events=trigger.events,
            pattern=trigger.pattern,
            debounce_seconds=debounce_seconds,
        )

        # Watch directory or parent of file
        if watch_path.is_dir():
            watch_dir = watch_path
            recursive = True
        else:
            watch_dir = watch_path.parent
            recursive = False

        watch = self._observer.schedule(
            handler,
            str(watch_dir),
            recursive=recursive,
        )

        self._watches[workflow_name] = watch
        self._handlers[workflow_name] = handler

        logger.info(
            f"Added file watch for workflow '{workflow_name}' on {watch_dir} "
            f"(pattern={trigger.pattern}, events={trigger.events})"
        )

        return f"file-watch:{workflow_name}"

    def remove_watch(self, workflow_name: str) -> bool:
        """Remove a file watch.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            True if removed, False if not found.
        """
        if workflow_name not in self._watches:
            return False

        # Cancel pending timers
        if workflow_name in self._handlers:
            self._handlers[workflow_name].cancel_all()
            del self._handlers[workflow_name]

        self._observer.unschedule(self._watches[workflow_name])
        del self._watches[workflow_name]

        logger.info(f"Removed file watch for workflow: {workflow_name}")
        return True

    def get_watches(self) -> list[dict[str, Any]]:
        """Get all active file watches.

        Returns:
            List of watch information dictionaries.
        """
        return [
            {
                "workflow": name,
                "path": str(watch.path),
                "recursive": watch.is_recursive,
            }
            for name, watch in self._watches.items()
        ]

    def get_watch(self, workflow_name: str) -> dict[str, Any] | None:
        """Get watch info for a specific workflow.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            Watch information or None if not found.
        """
        if workflow_name not in self._watches:
            return None

        watch = self._watches[workflow_name]
        return {
            "workflow": workflow_name,
            "path": str(watch.path),
            "recursive": watch.is_recursive,
        }


def _execute_file_watch_workflow(
    workflow_name: str,
    workflow_path: str,
    event_type: str,
    event_path: str,
    event_is_directory: bool,
) -> None:
    """Execute a workflow triggered by a file watch event.

    This is a module-level function to avoid serialization issues.

    Args:
        workflow_name: Name of the workflow.
        workflow_path: Path to the workflow file.
        event_type: Type of file event (created, modified, deleted).
        event_path: Path to the affected file.
        event_is_directory: Whether the event is for a directory.
    """
    from flowpilot.engine.parser import WorkflowParser

    if _global_runner is None:
        logger.error(f"Cannot execute workflow '{workflow_name}': no runner configured")
        return

    path = Path(workflow_path)
    if not path.exists():
        logger.error(f"Workflow file not found: {path}")
        return

    try:
        parser = WorkflowParser()
        workflow = parser.parse_file(path)

        # Pass file event info as special inputs
        inputs = {
            "_file_event": {
                "type": event_type,
                "path": event_path,
                "is_directory": event_is_directory,
                "timestamp": datetime.now().isoformat(),
            }
        }

        logger.info(
            f"Executing file-watch workflow '{workflow_name}' "
            f"(event={event_type}, path={event_path})"
        )

        # Run the async workflow in an event loop
        asyncio.run(
            _global_runner.run(
                workflow,
                inputs=inputs,
                workflow_path=str(path),
                trigger_type="file-watch",
            )
        )

        logger.info(f"Completed file-watch workflow: {workflow_name}")

    except Exception as e:
        logger.exception(f"Failed to execute file-watch workflow '{workflow_name}': {e}")

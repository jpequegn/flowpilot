"""Tests for FlowPilot trigger models."""

import pytest
from pydantic import ValidationError

from flowpilot.models import (
    CronTrigger,
    FileWatchTrigger,
    IntervalTrigger,
    ManualTrigger,
    WebhookTrigger,
)


class TestCronTrigger:
    """Tests for CronTrigger model."""

    def test_valid_5_field_cron(self) -> None:
        """Test valid 5-field cron expression."""
        trigger = CronTrigger(type="cron", schedule="0 9 * * 1-5")
        assert trigger.schedule == "0 9 * * 1-5"
        assert trigger.timezone == "local"

    def test_valid_6_field_cron(self) -> None:
        """Test valid 6-field cron expression (with seconds)."""
        trigger = CronTrigger(type="cron", schedule="0 30 9 * * 1-5")
        assert trigger.schedule == "0 30 9 * * 1-5"

    def test_cron_with_timezone(self) -> None:
        """Test cron with explicit timezone."""
        trigger = CronTrigger(type="cron", schedule="0 9 * * *", timezone="America/New_York")
        assert trigger.timezone == "America/New_York"

    def test_invalid_cron_too_few_fields(self) -> None:
        """Test cron with too few fields."""
        with pytest.raises(ValidationError) as exc_info:
            CronTrigger(type="cron", schedule="0 9 * *")
        assert "Cron expression must have 5 or 6 fields" in str(exc_info.value)

    def test_invalid_cron_too_many_fields(self) -> None:
        """Test cron with too many fields."""
        with pytest.raises(ValidationError) as exc_info:
            CronTrigger(type="cron", schedule="0 0 9 * * * 1-5")
        assert "Cron expression must have 5 or 6 fields" in str(exc_info.value)


class TestIntervalTrigger:
    """Tests for IntervalTrigger model."""

    def test_valid_seconds(self) -> None:
        """Test interval in seconds."""
        trigger = IntervalTrigger(type="interval", every="30s")
        assert trigger.every == "30s"
        assert trigger.to_seconds() == 30

    def test_valid_minutes(self) -> None:
        """Test interval in minutes."""
        trigger = IntervalTrigger(type="interval", every="5m")
        assert trigger.to_seconds() == 300

    def test_valid_hours(self) -> None:
        """Test interval in hours."""
        trigger = IntervalTrigger(type="interval", every="2h")
        assert trigger.to_seconds() == 7200

    def test_valid_days(self) -> None:
        """Test interval in days."""
        trigger = IntervalTrigger(type="interval", every="1d")
        assert trigger.to_seconds() == 86400

    def test_invalid_interval_format(self) -> None:
        """Test invalid interval format."""
        with pytest.raises(ValidationError) as exc_info:
            IntervalTrigger(type="interval", every="30")
        assert "Invalid interval format" in str(exc_info.value)

    def test_invalid_interval_unit(self) -> None:
        """Test invalid interval unit."""
        with pytest.raises(ValidationError) as exc_info:
            IntervalTrigger(type="interval", every="30w")
        assert "Invalid interval format" in str(exc_info.value)


class TestFileWatchTrigger:
    """Tests for FileWatchTrigger model."""

    def test_minimal_file_watch(self) -> None:
        """Test file watch with minimal config."""
        trigger = FileWatchTrigger(type="file-watch", path="~/Code/project")
        assert trigger.path == "~/Code/project"
        assert trigger.events == ["created"]
        assert trigger.pattern is None

    def test_file_watch_with_options(self) -> None:
        """Test file watch with all options."""
        trigger = FileWatchTrigger(
            type="file-watch",
            path="~/Code",
            events=["created", "modified", "deleted"],
            pattern="*.py",
        )
        assert trigger.events == ["created", "modified", "deleted"]
        assert trigger.pattern == "*.py"


class TestWebhookTrigger:
    """Tests for WebhookTrigger model."""

    def test_webhook_with_leading_slash(self) -> None:
        """Test webhook path with leading slash."""
        trigger = WebhookTrigger(type="webhook", path="/hooks/trigger")
        assert trigger.path == "/hooks/trigger"

    def test_webhook_without_leading_slash(self) -> None:
        """Test webhook path auto-prepends slash."""
        trigger = WebhookTrigger(type="webhook", path="hooks/trigger")
        assert trigger.path == "/hooks/trigger"

    def test_webhook_with_secret(self) -> None:
        """Test webhook with secret."""
        trigger = WebhookTrigger(type="webhook", path="/hooks/secure", secret="${WEBHOOK_SECRET}")
        assert trigger.secret == "${WEBHOOK_SECRET}"


class TestManualTrigger:
    """Tests for ManualTrigger model."""

    def test_manual_trigger(self) -> None:
        """Test manual trigger."""
        trigger = ManualTrigger(type="manual")
        assert trigger.type == "manual"

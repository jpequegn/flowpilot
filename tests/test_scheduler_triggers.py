"""Tests for scheduler trigger parsing."""

import pytest
from apscheduler.triggers.cron import CronTrigger as APCronTrigger
from apscheduler.triggers.interval import IntervalTrigger as APIntervalTrigger

from flowpilot.models.triggers import CronTrigger, IntervalTrigger, ManualTrigger
from flowpilot.scheduler.triggers import (
    is_schedulable,
    parse_cron_trigger,
    parse_interval_trigger,
    parse_trigger,
)


class TestParseCronTrigger:
    """Tests for parse_cron_trigger function."""

    def test_parse_5_field_cron(self) -> None:
        """Test parsing standard 5-field cron expression."""
        config = CronTrigger(type="cron", schedule="0 9 * * *")
        trigger = parse_cron_trigger(config)

        assert isinstance(trigger, APCronTrigger)

    def test_parse_6_field_cron(self) -> None:
        """Test parsing extended 6-field cron expression."""
        config = CronTrigger(type="cron", schedule="0 0 9 * * *")
        trigger = parse_cron_trigger(config)

        assert isinstance(trigger, APCronTrigger)

    def test_parse_cron_with_timezone(self) -> None:
        """Test parsing cron with timezone."""
        config = CronTrigger(type="cron", schedule="0 9 * * *", timezone="America/New_York")
        trigger = parse_cron_trigger(config)

        assert isinstance(trigger, APCronTrigger)
        assert str(trigger.timezone) == "America/New_York"

    def test_parse_cron_local_timezone(self) -> None:
        """Test parsing cron with local timezone (default)."""
        config = CronTrigger(type="cron", schedule="0 9 * * *", timezone="local")
        trigger = parse_cron_trigger(config)

        assert isinstance(trigger, APCronTrigger)
        # When timezone is None, APScheduler uses local time

    def test_parse_complex_cron(self) -> None:
        """Test parsing complex cron expressions."""
        # Every 15 minutes
        config = CronTrigger(type="cron", schedule="*/15 * * * *")
        trigger = parse_cron_trigger(config)
        assert isinstance(trigger, APCronTrigger)

        # Monday to Friday at 9am
        config = CronTrigger(type="cron", schedule="0 9 * * 1-5")
        trigger = parse_cron_trigger(config)
        assert isinstance(trigger, APCronTrigger)

        # First day of month at midnight
        config = CronTrigger(type="cron", schedule="0 0 1 * *")
        trigger = parse_cron_trigger(config)
        assert isinstance(trigger, APCronTrigger)

    def test_invalid_cron_too_few_fields(self) -> None:
        """Test that invalid cron with too few fields raises error."""
        # This should fail at Pydantic validation level
        with pytest.raises(ValueError, match="5 or 6 fields"):
            CronTrigger(type="cron", schedule="0 9 * *")

    def test_invalid_cron_too_many_fields(self) -> None:
        """Test that invalid cron with too many fields raises error."""
        with pytest.raises(ValueError, match="5 or 6 fields"):
            CronTrigger(type="cron", schedule="0 0 9 * * * *")


class TestParseIntervalTrigger:
    """Tests for parse_interval_trigger function."""

    def test_parse_seconds_interval(self) -> None:
        """Test parsing seconds interval."""
        config = IntervalTrigger(type="interval", every="30s")
        trigger = parse_interval_trigger(config)

        assert isinstance(trigger, APIntervalTrigger)
        assert trigger.interval.total_seconds() == 30

    def test_parse_minutes_interval(self) -> None:
        """Test parsing minutes interval."""
        config = IntervalTrigger(type="interval", every="5m")
        trigger = parse_interval_trigger(config)

        assert isinstance(trigger, APIntervalTrigger)
        assert trigger.interval.total_seconds() == 300

    def test_parse_hours_interval(self) -> None:
        """Test parsing hours interval."""
        config = IntervalTrigger(type="interval", every="2h")
        trigger = parse_interval_trigger(config)

        assert isinstance(trigger, APIntervalTrigger)
        assert trigger.interval.total_seconds() == 7200

    def test_parse_days_interval(self) -> None:
        """Test parsing days interval."""
        config = IntervalTrigger(type="interval", every="1d")
        trigger = parse_interval_trigger(config)

        assert isinstance(trigger, APIntervalTrigger)
        assert trigger.interval.total_seconds() == 86400

    def test_invalid_interval_format(self) -> None:
        """Test that invalid interval format raises error."""
        with pytest.raises(ValueError, match="Invalid interval format"):
            IntervalTrigger(type="interval", every="5min")

    def test_invalid_interval_no_unit(self) -> None:
        """Test that interval without unit raises error."""
        with pytest.raises(ValueError, match="Invalid interval format"):
            IntervalTrigger(type="interval", every="30")


class TestParseTrigger:
    """Tests for parse_trigger function."""

    def test_parse_cron_trigger(self) -> None:
        """Test parsing cron trigger through generic function."""
        config = CronTrigger(type="cron", schedule="0 9 * * *")
        trigger = parse_trigger(config)

        assert isinstance(trigger, APCronTrigger)

    def test_parse_interval_trigger(self) -> None:
        """Test parsing interval trigger through generic function."""
        config = IntervalTrigger(type="interval", every="5m")
        trigger = parse_trigger(config)

        assert isinstance(trigger, APIntervalTrigger)

    def test_parse_non_schedulable_trigger(self) -> None:
        """Test that non-schedulable trigger raises error."""
        config = ManualTrigger(type="manual")

        with pytest.raises(ValueError, match="Cannot schedule trigger type"):
            parse_trigger(config)


class TestIsSchedulable:
    """Tests for is_schedulable function."""

    def test_cron_is_schedulable(self) -> None:
        """Test that cron trigger is schedulable."""
        config = CronTrigger(type="cron", schedule="0 9 * * *")
        assert is_schedulable(config) is True

    def test_interval_is_schedulable(self) -> None:
        """Test that interval trigger is schedulable."""
        config = IntervalTrigger(type="interval", every="5m")
        assert is_schedulable(config) is True

    def test_manual_not_schedulable(self) -> None:
        """Test that manual trigger is not schedulable."""
        config = ManualTrigger(type="manual")
        assert is_schedulable(config) is False

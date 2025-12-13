"""Trigger parsing utilities for APScheduler integration."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger as APCronTrigger
from apscheduler.triggers.interval import IntervalTrigger as APIntervalTrigger

if TYPE_CHECKING:
    from flowpilot.models.triggers import CronTrigger, IntervalTrigger, Trigger


def parse_cron_trigger(config: CronTrigger) -> APCronTrigger:
    """Parse cron trigger from workflow config to APScheduler trigger.

    Args:
        config: CronTrigger configuration from workflow.

    Returns:
        APScheduler CronTrigger instance.

    Raises:
        ValueError: If cron expression is invalid.
    """
    parts = config.schedule.split()

    # Determine timezone
    timezone = config.timezone if config.timezone != "local" else None

    if len(parts) == 5:
        # Standard cron: minute hour day month day_of_week
        minute, hour, day, month, day_of_week = parts
        return APCronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=timezone,
        )
    elif len(parts) == 6:
        # Extended cron: second minute hour day month day_of_week
        second, minute, hour, day, month, day_of_week = parts
        return APCronTrigger(
            second=second,
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=timezone,
        )
    else:
        msg = f"Invalid cron expression: {config.schedule}. Expected 5 or 6 fields."
        raise ValueError(msg)


def parse_interval_trigger(config: IntervalTrigger) -> APIntervalTrigger:
    """Parse interval trigger from workflow config to APScheduler trigger.

    Args:
        config: IntervalTrigger configuration from workflow.

    Returns:
        APScheduler IntervalTrigger instance.

    Raises:
        ValueError: If interval format is invalid.
    """
    match = re.match(r"^(\d+)(s|m|h|d)$", config.every)
    if not match:
        msg = f"Invalid interval: {config.every}. Use format like '30s', '5m', '2h', '1d'"
        raise ValueError(msg)

    value = int(match.group(1))
    unit = match.group(2)

    kwargs: dict[str, int] = {
        "s": {"seconds": value},
        "m": {"minutes": value},
        "h": {"hours": value},
        "d": {"days": value},
    }[unit]

    return APIntervalTrigger(**kwargs)


def parse_trigger(trigger_config: Trigger) -> APCronTrigger | APIntervalTrigger:
    """Parse any schedulable trigger type to APScheduler trigger.

    Args:
        trigger_config: Trigger configuration from workflow.

    Returns:
        APScheduler trigger instance.

    Raises:
        ValueError: If trigger type is not schedulable.
    """
    # Import here to avoid circular imports
    from flowpilot.models.triggers import CronTrigger, IntervalTrigger

    if isinstance(trigger_config, CronTrigger):
        return parse_cron_trigger(trigger_config)
    elif isinstance(trigger_config, IntervalTrigger):
        return parse_interval_trigger(trigger_config)
    else:
        msg = f"Cannot schedule trigger type: {trigger_config.type}"
        raise ValueError(msg)


def is_schedulable(trigger_config: Trigger) -> bool:
    """Check if a trigger type can be scheduled.

    Args:
        trigger_config: Trigger configuration from workflow.

    Returns:
        True if trigger can be scheduled with APScheduler.
    """
    return trigger_config.type in ("cron", "interval")

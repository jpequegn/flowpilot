"""Jinja2 template engine for FlowPilot workflows."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

if TYPE_CHECKING:
    from .context import ExecutionContext


class TemplateEngine:
    """Sandboxed Jinja2 template engine for workflow templating."""

    def __init__(self) -> None:
        """Initialize the template engine with sandbox environment."""
        self.env = SandboxedEnvironment(
            undefined=StrictUndefined,
            autoescape=False,
        )
        # Add custom filters
        self.env.filters["truncate"] = self._truncate
        self.env.filters["json"] = self._to_json
        self.env.filters["lines"] = self._to_lines
        self.env.filters["first_line"] = self._first_line
        self.env.filters["last_line"] = self._last_line
        self.env.filters["strip"] = self._strip
        self.env.filters["lower"] = str.lower
        self.env.filters["upper"] = str.upper
        self.env.filters["split"] = self._split

    def render(self, template: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template string.

        Args:
            template: Template string with Jinja2 syntax.
            context: Context dictionary for template variables.

        Returns:
            Rendered string.
        """
        tpl = self.env.from_string(template)
        return tpl.render(**context)

    def render_value(self, value: Any, context: dict[str, Any]) -> Any:
        """Recursively render template values in data structures.

        Args:
            value: Value to render (string, dict, list, or other).
            context: Context dictionary for template variables.

        Returns:
            Rendered value with templates expanded.
        """
        if isinstance(value, str):
            # Only render if it looks like it contains a template
            if "{{" in value or "{%" in value:
                return self.render(value, context)
            return value
        elif isinstance(value, dict):
            return {k: self.render_value(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.render_value(item, context) for item in value]
        else:
            return value

    def render_dict(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Render all template strings in a dictionary.

        Args:
            data: Dictionary with potential template strings.
            context: Context dictionary for template variables.

        Returns:
            Dictionary with templates rendered.
        """
        result = self.render_value(data, context)
        if not isinstance(result, dict):
            raise TypeError("render_dict expects a dict input")
        return result

    def render_with_context(self, template: str, execution_context: ExecutionContext) -> str:
        """Render a template using an ExecutionContext.

        Args:
            template: Template string with Jinja2 syntax.
            execution_context: Execution context with inputs and node results.

        Returns:
            Rendered string.
        """
        return self.render(template, execution_context.get_template_context())

    def has_template(self, value: str) -> bool:
        """Check if a string contains Jinja2 template syntax."""
        return bool(re.search(r"\{\{.*?\}\}|\{%.*?%\}", value))

    # Custom filters

    @staticmethod
    def _truncate(value: str, length: int = 80, suffix: str = "...") -> str:
        """Truncate a string to a maximum length."""
        if len(value) <= length:
            return value
        return value[: length - len(suffix)] + suffix

    @staticmethod
    def _to_json(value: Any, indent: int | None = None) -> str:
        """Convert value to JSON string."""
        return json.dumps(value, indent=indent, default=str)

    @staticmethod
    def _to_lines(value: str) -> list[str]:
        """Split string into lines."""
        return value.splitlines()

    @staticmethod
    def _first_line(value: str) -> str:
        """Get the first line of a string."""
        lines = value.splitlines()
        return lines[0] if lines else ""

    @staticmethod
    def _last_line(value: str) -> str:
        """Get the last line of a string."""
        lines = value.splitlines()
        return lines[-1] if lines else ""

    @staticmethod
    def _strip(value: str) -> str:
        """Strip whitespace from both ends."""
        return value.strip()

    @staticmethod
    def _split(value: str, sep: str | None = None) -> list[str]:
        """Split string by separator."""
        return value.split(sep)

"""Tests for FlowPilot template engine."""

import pytest
from jinja2 import UndefinedError

from flowpilot.engine import ExecutionContext, NodeResult, TemplateEngine


class TestTemplateEngine:
    """Tests for TemplateEngine class."""

    @pytest.fixture
    def engine(self) -> TemplateEngine:
        """Create a template engine instance."""
        return TemplateEngine()

    def test_render_simple_template(self, engine: TemplateEngine) -> None:
        """Test rendering simple template."""
        result = engine.render("Hello, {{ name }}!", {"name": "World"})
        assert result == "Hello, World!"

    def test_render_with_inputs(self, engine: TemplateEngine) -> None:
        """Test rendering template with inputs context."""
        context = {"inputs": {"greeting": "Hi", "target": "there"}}
        result = engine.render("{{ inputs.greeting }}, {{ inputs.target }}!", context)
        assert result == "Hi, there!"

    def test_render_with_node_output(self, engine: TemplateEngine) -> None:
        """Test rendering template with node output."""
        context = {
            "nodes": {
                "step_1": {
                    "stdout": "Hello from step 1",
                    "output": "parsed output",
                }
            }
        }
        result = engine.render("Previous: {{ nodes.step_1.stdout }}", context)
        assert result == "Previous: Hello from step 1"

    def test_render_undefined_raises(self, engine: TemplateEngine) -> None:
        """Test that undefined variables raise error."""
        with pytest.raises(UndefinedError):
            engine.render("{{ undefined_var }}", {})

    def test_render_value_string(self, engine: TemplateEngine) -> None:
        """Test rendering string value."""
        result = engine.render_value("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"

    def test_render_value_dict(self, engine: TemplateEngine) -> None:
        """Test rendering dict with template values."""
        data = {
            "command": "echo {{ message }}",
            "static": "no templates here",
        }
        result = engine.render_value(data, {"message": "hello"})
        assert result["command"] == "echo hello"
        assert result["static"] == "no templates here"

    def test_render_value_list(self, engine: TemplateEngine) -> None:
        """Test rendering list with template values."""
        data = ["{{ a }}", "{{ b }}", "static"]
        result = engine.render_value(data, {"a": "x", "b": "y"})
        assert result == ["x", "y", "static"]

    def test_render_value_nested(self, engine: TemplateEngine) -> None:
        """Test rendering nested structures."""
        data = {
            "outer": {
                "inner": "{{ value }}",
                "list": ["{{ item }}"],
            }
        }
        result = engine.render_value(data, {"value": "nested", "item": "list-item"})
        assert result["outer"]["inner"] == "nested"
        assert result["outer"]["list"] == ["list-item"]

    def test_render_value_non_template_string(self, engine: TemplateEngine) -> None:
        """Test non-template strings are passed through."""
        result = engine.render_value("plain string", {})
        assert result == "plain string"

    def test_render_value_non_string(self, engine: TemplateEngine) -> None:
        """Test non-string values are passed through."""
        assert engine.render_value(42, {}) == 42
        assert engine.render_value(3.14, {}) == 3.14
        assert engine.render_value(True, {}) is True
        assert engine.render_value(None, {}) is None

    def test_render_dict(self, engine: TemplateEngine) -> None:
        """Test render_dict method."""
        data = {"cmd": "{{ cmd }}", "timeout": 30}
        result = engine.render_dict(data, {"cmd": "ls -la"})
        assert result["cmd"] == "ls -la"
        assert result["timeout"] == 30

    def test_has_template_true(self, engine: TemplateEngine) -> None:
        """Test has_template detection."""
        assert engine.has_template("{{ var }}")
        assert engine.has_template("Hello {{ name }}")
        assert engine.has_template("{% if x %}yes{% endif %}")

    def test_has_template_false(self, engine: TemplateEngine) -> None:
        """Test has_template for plain strings."""
        assert not engine.has_template("plain text")
        assert not engine.has_template("no templates")
        assert not engine.has_template("")


class TestTemplateFilters:
    """Tests for custom template filters."""

    @pytest.fixture
    def engine(self) -> TemplateEngine:
        """Create a template engine instance."""
        return TemplateEngine()

    def test_truncate_filter(self, engine: TemplateEngine) -> None:
        """Test truncate filter."""
        result = engine.render(
            "{{ text | truncate(10) }}",
            {"text": "This is a very long string"},
        )
        assert result == "This is..."
        assert len(result) == 10

    def test_truncate_filter_short_string(self, engine: TemplateEngine) -> None:
        """Test truncate filter with short string."""
        result = engine.render("{{ text | truncate(50) }}", {"text": "Short"})
        assert result == "Short"

    def test_json_filter(self, engine: TemplateEngine) -> None:
        """Test json filter."""
        result = engine.render(
            "{{ data | json }}",
            {"data": {"key": "value"}},
        )
        assert result == '{"key": "value"}'

    def test_json_filter_with_indent(self, engine: TemplateEngine) -> None:
        """Test json filter with indent."""
        result = engine.render(
            "{{ data | json(2) }}",
            {"data": {"key": "value"}},
        )
        assert '"key": "value"' in result
        assert "\n" in result

    def test_lines_filter(self, engine: TemplateEngine) -> None:
        """Test lines filter."""
        result = engine.render(
            "{{ text | lines }}",
            {"text": "line1\nline2\nline3"},
        )
        assert result == "['line1', 'line2', 'line3']"

    def test_first_line_filter(self, engine: TemplateEngine) -> None:
        """Test first_line filter."""
        result = engine.render(
            "{{ text | first_line }}",
            {"text": "first\nsecond\nthird"},
        )
        assert result == "first"

    def test_last_line_filter(self, engine: TemplateEngine) -> None:
        """Test last_line filter."""
        result = engine.render(
            "{{ text | last_line }}",
            {"text": "first\nsecond\nthird"},
        )
        assert result == "third"

    def test_strip_filter(self, engine: TemplateEngine) -> None:
        """Test strip filter."""
        result = engine.render(
            "{{ text | strip }}",
            {"text": "  padded  "},
        )
        assert result == "padded"

    def test_lower_filter(self, engine: TemplateEngine) -> None:
        """Test lower filter."""
        result = engine.render("{{ text | lower }}", {"text": "HELLO"})
        assert result == "hello"

    def test_upper_filter(self, engine: TemplateEngine) -> None:
        """Test upper filter."""
        result = engine.render("{{ text | upper }}", {"text": "hello"})
        assert result == "HELLO"

    def test_split_filter(self, engine: TemplateEngine) -> None:
        """Test split filter."""
        result = engine.render(
            "{{ text | split(',') }}",
            {"text": "a,b,c"},
        )
        assert result == "['a', 'b', 'c']"


class TestTemplateWithExecutionContext:
    """Tests for template rendering with ExecutionContext."""

    @pytest.fixture
    def engine(self) -> TemplateEngine:
        """Create a template engine instance."""
        return TemplateEngine()

    def test_render_with_execution_context(self, engine: TemplateEngine) -> None:
        """Test rendering with ExecutionContext."""
        context = ExecutionContext(
            workflow_name="test",
            inputs={"name": "FlowPilot"},
        )
        context.set_node_result(
            "step-1",
            NodeResult.success(stdout="Hello"),
        )

        result = engine.render_with_context(
            "{{ inputs.name }}: {{ nodes.step_1.stdout }}",
            context,
        )
        assert result == "FlowPilot: Hello"

    def test_render_date_function(self, engine: TemplateEngine) -> None:
        """Test date function in templates."""
        context = ExecutionContext(workflow_name="test")

        result = engine.render_with_context(
            "{{ date('%Y') }}",
            context,
        )
        assert len(result) == 4  # Year format

    def test_render_env_variable(self, engine: TemplateEngine) -> None:
        """Test accessing environment variables."""
        context = ExecutionContext(workflow_name="test")

        # PATH should be available on all systems
        result = engine.render_with_context(
            "{% if env.PATH %}has path{% endif %}",
            context,
        )
        assert result == "has path"

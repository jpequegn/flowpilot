"""Tests for HTTP node executor."""

import pytest
from pytest_httpx import HTTPXMock

from flowpilot.engine import ExecutionContext
from flowpilot.engine.nodes import HttpExecutor
from flowpilot.models import HttpNode


@pytest.fixture
def executor() -> HttpExecutor:
    """Create an HTTP executor instance."""
    return HttpExecutor()


@pytest.fixture
def context() -> ExecutionContext:
    """Create an execution context."""
    return ExecutionContext(workflow_name="test")


class TestHttpExecutor:
    """Tests for HttpExecutor."""

    @pytest.mark.asyncio
    async def test_execute_get_request(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test executing a simple GET request."""
        httpx_mock.add_response(
            url="https://api.example.com/data",
            json={"status": "ok", "value": 42},
        )

        node = HttpNode(
            type="http",
            id="get-test",
            url="https://api.example.com/data",
            method="GET",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["status_code"] == 200
        assert result.data["body"]["status"] == "ok"
        assert result.data["body"]["value"] == 42
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_post_request_with_json_body(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test executing a POST request with JSON body."""
        httpx_mock.add_response(
            url="https://api.example.com/create",
            json={"id": 123, "created": True},
        )

        node = HttpNode(
            type="http",
            id="post-test",
            url="https://api.example.com/create",
            method="POST",
            body={"name": "test", "value": 100},
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["status_code"] == 200
        assert result.data["body"]["id"] == 123
        assert result.data["body"]["created"] is True

    @pytest.mark.asyncio
    async def test_execute_post_request_with_string_body(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test executing a POST request with string body."""
        httpx_mock.add_response(
            url="https://api.example.com/raw",
            text="OK",
        )

        node = HttpNode(
            type="http",
            id="post-string-test",
            url="https://api.example.com/raw",
            method="POST",
            body="raw data content",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_execute_with_custom_headers(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test request with custom headers."""
        httpx_mock.add_response(
            url="https://api.example.com/auth",
            json={"authenticated": True},
        )

        node = HttpNode(
            type="http",
            id="headers-test",
            url="https://api.example.com/auth",
            method="GET",
            headers={"Authorization": "Bearer token123", "X-Custom": "value"},
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        # Verify headers were sent
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == "Bearer token123"
        assert request.headers["X-Custom"] == "value"

    @pytest.mark.asyncio
    async def test_execute_put_request(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test executing a PUT request."""
        httpx_mock.add_response(
            url="https://api.example.com/update/1",
            json={"updated": True},
        )

        node = HttpNode(
            type="http",
            id="put-test",
            url="https://api.example.com/update/1",
            method="PUT",
            body={"name": "updated"},
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "PUT"

    @pytest.mark.asyncio
    async def test_execute_delete_request(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test executing a DELETE request."""
        httpx_mock.add_response(
            url="https://api.example.com/delete/1",
            json={"deleted": True},
        )

        node = HttpNode(
            type="http",
            id="delete-test",
            url="https://api.example.com/delete/1",
            method="DELETE",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "DELETE"

    @pytest.mark.asyncio
    async def test_execute_patch_request(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test executing a PATCH request."""
        httpx_mock.add_response(
            url="https://api.example.com/patch/1",
            json={"patched": True},
        )

        node = HttpNode(
            type="http",
            id="patch-test",
            url="https://api.example.com/patch/1",
            method="PATCH",
            body={"field": "new_value"},
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "PATCH"

    @pytest.mark.asyncio
    async def test_execute_http_error_response(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test handling HTTP error response (4xx/5xx)."""
        httpx_mock.add_response(
            url="https://api.example.com/error",
            status_code=404,
            json={"error": "Not Found"},
        )

        node = HttpNode(
            type="http",
            id="error-test",
            url="https://api.example.com/error",
            method="GET",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.data["status_code"] == 404
        assert result.error_message is not None
        assert "404" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_server_error_response(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test handling server error (5xx)."""
        httpx_mock.add_response(
            url="https://api.example.com/server-error",
            status_code=500,
            json={"error": "Internal Server Error"},
        )

        node = HttpNode(
            type="http",
            id="server-error-test",
            url="https://api.example.com/server-error",
            method="GET",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.data["status_code"] == 500
        assert result.error_message is not None
        assert "500" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_non_json_response(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test handling non-JSON response."""
        httpx_mock.add_response(
            url="https://api.example.com/html",
            text="<html><body>Hello</body></html>",
            headers={"Content-Type": "text/html"},
        )

        node = HttpNode(
            type="http",
            id="html-test",
            url="https://api.example.com/html",
            method="GET",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["body"]["text"] == "<html><body>Hello</body></html>"
        assert "<html>" in result.output

    @pytest.mark.asyncio
    async def test_execute_timeout(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test request timeout handling."""
        import httpx

        httpx_mock.add_exception(httpx.TimeoutException("Connection timed out"))

        node = HttpNode(
            type="http",
            id="timeout-test",
            url="https://api.example.com/slow",
            method="GET",
            timeout=1,
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_connection_error(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test connection error handling."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        node = HttpNode(
            type="http",
            id="connection-test",
            url="https://api.example.com/unreachable",
            method="GET",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "connection" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_response_headers_captured(
        self, executor: HttpExecutor, context: ExecutionContext, httpx_mock: HTTPXMock
    ) -> None:
        """Test that response headers are captured."""
        httpx_mock.add_response(
            url="https://api.example.com/headers",
            json={"data": "value"},
            headers={"X-Custom-Header": "custom-value", "X-Rate-Limit": "100"},
        )

        node = HttpNode(
            type="http",
            id="response-headers-test",
            url="https://api.example.com/headers",
            method="GET",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert "headers" in result.data
        assert result.data["headers"]["x-custom-header"] == "custom-value"
        assert result.data["headers"]["x-rate-limit"] == "100"

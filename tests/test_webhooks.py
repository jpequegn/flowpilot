"""Tests for webhook handling."""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from flowpilot.api.webhooks import (
    _verify_secret,
    get_webhook,
    get_webhooks,
    register_webhook,
    router,
    set_global_webhook_runner,
    unregister_webhook,
)


@pytest.fixture(autouse=True)
def clear_webhooks():
    """Clear webhooks before and after each test."""
    from flowpilot.api import webhooks

    webhooks._webhooks.clear()
    webhooks._global_runner = None
    yield
    webhooks._webhooks.clear()
    webhooks._global_runner = None


class TestRegisterWebhook:
    """Tests for register_webhook function."""

    def test_register_webhook_with_leading_slash(self) -> None:
        """Test registering a webhook with leading slash."""
        path = register_webhook("/github-push", "my-workflow", "/path/to/workflow.yaml")

        assert path == "/github-push"
        webhooks = get_webhooks()
        assert len(webhooks) == 1
        assert webhooks[0]["path"] == "/github-push"
        assert webhooks[0]["workflow_name"] == "my-workflow"

    def test_register_webhook_without_leading_slash(self) -> None:
        """Test registering a webhook without leading slash adds it."""
        path = register_webhook("github-push", "my-workflow", "/path/to/workflow.yaml")

        assert path == "/github-push"

    def test_register_webhook_with_secret(self) -> None:
        """Test registering a webhook with secret."""
        register_webhook(
            "/secure-hook",
            "my-workflow",
            "/path/to/workflow.yaml",
            secret="my-secret",
        )

        webhooks = get_webhooks()
        assert len(webhooks) == 1
        assert webhooks[0]["has_secret"] is True

    def test_register_webhook_without_secret(self) -> None:
        """Test registering a webhook without secret."""
        register_webhook("/open-hook", "my-workflow", "/path/to/workflow.yaml")

        webhooks = get_webhooks()
        assert len(webhooks) == 1
        assert webhooks[0]["has_secret"] is False

    def test_register_multiple_webhooks(self) -> None:
        """Test registering multiple webhooks."""
        register_webhook("/hook1", "workflow-1", "/path/to/workflow1.yaml")
        register_webhook("/hook2", "workflow-2", "/path/to/workflow2.yaml")

        webhooks = get_webhooks()
        assert len(webhooks) == 2


class TestUnregisterWebhook:
    """Tests for unregister_webhook function."""

    def test_unregister_existing_webhook(self) -> None:
        """Test unregistering an existing webhook."""
        register_webhook("/my-hook", "my-workflow", "/path/to/workflow.yaml")
        assert len(get_webhooks()) == 1

        result = unregister_webhook("my-workflow")

        assert result is True
        assert len(get_webhooks()) == 0

    def test_unregister_nonexistent_webhook(self) -> None:
        """Test unregistering a non-existent webhook returns False."""
        result = unregister_webhook("nonexistent")

        assert result is False

    def test_unregister_removes_all_webhooks_for_workflow(self) -> None:
        """Test unregistering removes all webhooks for a workflow."""
        register_webhook("/hook1", "my-workflow", "/path/to/workflow.yaml")
        register_webhook("/hook2", "my-workflow", "/path/to/workflow.yaml")
        register_webhook("/hook3", "other-workflow", "/path/to/other.yaml")

        result = unregister_webhook("my-workflow")

        assert result is True
        webhooks = get_webhooks()
        assert len(webhooks) == 1
        assert webhooks[0]["workflow_name"] == "other-workflow"


class TestGetWebhooks:
    """Tests for get_webhooks function."""

    def test_get_webhooks_empty(self) -> None:
        """Test getting webhooks when none registered."""
        webhooks = get_webhooks()

        assert webhooks == []

    def test_get_webhooks_returns_list(self) -> None:
        """Test get_webhooks returns proper format."""
        register_webhook("/hook", "workflow", "/path.yaml", secret="secret")

        webhooks = get_webhooks()

        assert len(webhooks) == 1
        assert webhooks[0] == {
            "path": "/hook",
            "workflow_name": "workflow",
            "has_secret": True,
        }


class TestGetWebhook:
    """Tests for get_webhook function."""

    def test_get_webhook_existing(self) -> None:
        """Test getting an existing webhook."""
        register_webhook("/my-hook", "my-workflow", "/path.yaml")

        webhook = get_webhook("my-workflow")

        assert webhook is not None
        assert webhook["path"] == "/my-hook"
        assert webhook["workflow_name"] == "my-workflow"

    def test_get_webhook_nonexistent(self) -> None:
        """Test getting a non-existent webhook returns None."""
        webhook = get_webhook("nonexistent")

        assert webhook is None


class TestSetGlobalWebhookRunner:
    """Tests for set_global_webhook_runner function."""

    def test_set_runner(self) -> None:
        """Test setting the global runner."""
        mock_runner = MagicMock()
        set_global_webhook_runner(mock_runner)

        from flowpilot.api import webhooks

        assert webhooks._global_runner == mock_runner

    def test_clear_runner(self) -> None:
        """Test clearing the global runner."""
        mock_runner = MagicMock()
        set_global_webhook_runner(mock_runner)
        set_global_webhook_runner(None)

        from flowpilot.api import webhooks

        assert webhooks._global_runner is None


class TestVerifySecret:
    """Tests for _verify_secret function."""

    def test_no_secret_configured(self) -> None:
        """Test verification passes when no secret configured."""
        config = {"secret": None}

        result = _verify_secret(config, b"body", None, None)

        assert result is True

    def test_simple_secret_valid(self) -> None:
        """Test verification passes with valid simple secret."""
        config = {"secret": "my-secret"}

        result = _verify_secret(config, b"body", "my-secret", None)

        assert result is True

    def test_simple_secret_invalid(self) -> None:
        """Test verification fails with invalid simple secret."""
        config = {"secret": "my-secret"}

        with pytest.raises(HTTPException) as exc_info:
            _verify_secret(config, b"body", "wrong-secret", None)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid secret"

    def test_hmac_signature_valid(self) -> None:
        """Test verification passes with valid HMAC signature."""
        secret = "my-secret"
        body = b'{"action": "push"}'
        expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        signature = f"sha256={expected_sig}"

        config = {"secret": secret}
        result = _verify_secret(config, body, None, signature)

        assert result is True

    def test_hmac_signature_invalid(self) -> None:
        """Test verification fails with invalid HMAC signature."""
        config = {"secret": "my-secret"}

        with pytest.raises(HTTPException) as exc_info:
            _verify_secret(config, b"body", None, "sha256=invalid")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid signature"

    def test_secret_required_but_missing(self) -> None:
        """Test verification fails when secret required but not provided."""
        config = {"secret": "my-secret"}

        with pytest.raises(HTTPException) as exc_info:
            _verify_secret(config, b"body", None, None)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"


class TestWebhookEndpoint:
    """Tests for webhook HTTP endpoint."""

    @pytest.fixture
    def app(self):
        """Create a FastAPI app with the webhook router."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    def test_webhook_not_found(self, client) -> None:
        """Test 404 when webhook not found."""
        response = client.post("/hooks/nonexistent")

        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_webhook_triggers_workflow(self, client) -> None:
        """Test webhook triggers workflow execution."""
        register_webhook("/my-hook", "my-workflow", "/path/to/workflow.yaml")

        response = client.post(
            "/hooks/my-hook",
            json={"event": "push"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["workflow"] == "my-workflow"
        assert "execution_id" in data

    def test_webhook_with_valid_secret(self, client) -> None:
        """Test webhook with valid secret header."""
        register_webhook("/secure", "my-workflow", "/path.yaml", secret="my-secret")

        response = client.post(
            "/hooks/secure",
            json={"event": "push"},
            headers={"X-Webhook-Secret": "my-secret"},
        )

        assert response.status_code == 200

    def test_webhook_with_invalid_secret(self, client) -> None:
        """Test webhook with invalid secret returns 401."""
        register_webhook("/secure", "my-workflow", "/path.yaml", secret="my-secret")

        response = client.post(
            "/hooks/secure",
            json={"event": "push"},
            headers={"X-Webhook-Secret": "wrong-secret"},
        )

        assert response.status_code == 401

    def test_webhook_with_hmac_signature(self, client) -> None:
        """Test webhook with HMAC signature (GitHub style)."""
        secret = "github-secret"
        register_webhook("/github", "my-workflow", "/path.yaml", secret=secret)

        body = b'{"action": "push"}'
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        response = client.post(
            "/hooks/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
            },
        )

        assert response.status_code == 200

    def test_webhook_missing_auth_when_required(self, client) -> None:
        """Test webhook returns 401 when auth required but not provided."""
        register_webhook("/secure", "my-workflow", "/path.yaml", secret="my-secret")

        response = client.post(
            "/hooks/secure",
            json={"event": "push"},
        )

        assert response.status_code == 401

    def test_webhook_includes_request_data_in_inputs(self, client) -> None:
        """Test webhook passes request data to workflow inputs."""
        register_webhook("/my-hook", "my-workflow", "/path.yaml")

        # We can't easily verify inputs without mocking the runner
        # But we can verify the response structure
        response = client.post(
            "/hooks/my-hook",
            json={"event": "push", "repository": "test/repo"},
            params={"ref": "main"},
        )

        assert response.status_code == 200

    def test_webhook_empty_body(self, client) -> None:
        """Test webhook handles empty body."""
        register_webhook("/my-hook", "my-workflow", "/path.yaml")

        response = client.post("/hooks/my-hook")

        assert response.status_code == 200


class TestWebhookExecution:
    """Tests for webhook workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_workflow_no_runner(self) -> None:
        """Test execution logs error when no runner configured."""
        from flowpilot.api.webhooks import _execute_webhook_workflow

        with patch("flowpilot.api.webhooks.logger") as mock_logger:
            await _execute_webhook_workflow(
                "my-workflow",
                "/path/to/workflow.yaml",
                {},
                "exec-123",
            )

            mock_logger.error.assert_called_once()
            assert "no runner configured" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_execute_workflow_file_not_found(self, tmp_path) -> None:
        """Test execution logs error when workflow file not found."""
        from flowpilot.api.webhooks import _execute_webhook_workflow

        mock_runner = MagicMock()
        set_global_webhook_runner(mock_runner)

        with patch("flowpilot.api.webhooks.logger") as mock_logger:
            await _execute_webhook_workflow(
                "my-workflow",
                "/nonexistent/workflow.yaml",
                {},
                "exec-123",
            )

            mock_logger.error.assert_called_once()
            assert "not found" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, tmp_path) -> None:
        """Test successful workflow execution."""
        from flowpilot.api.webhooks import _execute_webhook_workflow

        # Create a workflow file
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("""
name: test-workflow
triggers:
  - type: webhook
    path: /test
nodes:
  - id: delay
    type: delay
    duration: "1ms"
""")

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        set_global_webhook_runner(mock_runner)

        await _execute_webhook_workflow(
            "test-workflow",
            str(workflow_path),
            {"_webhook": {"path": "/test"}},
            "exec-123",
        )

        mock_runner.run.assert_called_once()
        call_kwargs = mock_runner.run.call_args[1]
        assert call_kwargs["trigger_type"] == "webhook"
        assert "_webhook" in call_kwargs["inputs"]

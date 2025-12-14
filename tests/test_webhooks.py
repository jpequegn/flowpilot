"""Tests for webhook service."""

import hashlib
import hmac
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flowpilot.api.webhooks import (
    WebhookService,
    _resolve_secret,
    _verify_signature,
    get_webhook,
    get_webhooks,
    register_webhook,
    router,
    set_global_webhook_runner,
    unregister_webhook,
)
from flowpilot.models.triggers import WebhookTrigger


@pytest.fixture
def clean_webhooks():
    """Clean up webhooks before and after each test."""
    from flowpilot.api import webhooks

    # Clear webhooks before test
    webhooks._webhooks.clear()
    yield
    # Clear webhooks after test
    webhooks._webhooks.clear()


@pytest.fixture
def app():
    """Create a FastAPI app with webhook router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app, clean_webhooks):
    """Create a test client."""
    return TestClient(app)


class TestRegisterWebhook:
    """Tests for webhook registration."""

    def test_register_webhook_basic(self, clean_webhooks) -> None:
        """Test basic webhook registration."""
        webhook_id = register_webhook(
            path="/test-hook",
            workflow_name="test-workflow",
            workflow_path="/path/to/workflow.yaml",
        )

        assert webhook_id == "webhook:test-workflow:/test-hook"
        assert len(get_webhooks()) == 1

    def test_register_webhook_normalizes_path(self, clean_webhooks) -> None:
        """Test that paths are normalized to start with /."""
        register_webhook(
            path="no-slash",
            workflow_name="test-workflow",
            workflow_path="/path/to/workflow.yaml",
        )

        webhooks = get_webhooks()
        assert webhooks[0]["path"] == "/no-slash"

    def test_register_webhook_with_secret(self, clean_webhooks) -> None:
        """Test webhook registration with secret."""
        register_webhook(
            path="/secure-hook",
            workflow_name="secure-workflow",
            workflow_path="/path/to/workflow.yaml",
            secret="my-secret",
        )

        webhooks = get_webhooks()
        assert webhooks[0]["has_secret"] is True

    def test_register_webhook_with_env_secret(self, clean_webhooks) -> None:
        """Test webhook registration with environment variable secret."""
        os.environ["TEST_WEBHOOK_SECRET"] = "env-secret-value"
        try:
            register_webhook(
                path="/env-hook",
                workflow_name="env-workflow",
                workflow_path="/path/to/workflow.yaml",
                secret="${TEST_WEBHOOK_SECRET}",
            )

            webhooks = get_webhooks()
            assert webhooks[0]["has_secret"] is True
        finally:
            del os.environ["TEST_WEBHOOK_SECRET"]


class TestUnregisterWebhook:
    """Tests for webhook unregistration."""

    def test_unregister_webhook(self, clean_webhooks) -> None:
        """Test webhook unregistration."""
        register_webhook("/hook1", "workflow1", "/path1.yaml")
        register_webhook("/hook2", "workflow2", "/path2.yaml")

        result = unregister_webhook("workflow1")

        assert result is True
        assert len(get_webhooks()) == 1
        assert get_webhooks()[0]["workflow_name"] == "workflow2"

    def test_unregister_nonexistent_webhook(self, clean_webhooks) -> None:
        """Test unregistering a non-existent webhook."""
        result = unregister_webhook("nonexistent")
        assert result is False

    def test_unregister_removes_all_for_workflow(self, clean_webhooks) -> None:
        """Test that unregister removes all webhooks for a workflow."""
        register_webhook("/hook1", "workflow1", "/path1.yaml")
        register_webhook("/hook2", "workflow1", "/path2.yaml")
        register_webhook("/hook3", "workflow2", "/path3.yaml")

        unregister_webhook("workflow1")

        webhooks = get_webhooks()
        assert len(webhooks) == 1
        assert webhooks[0]["workflow_name"] == "workflow2"


class TestGetWebhooks:
    """Tests for getting webhooks."""

    def test_get_webhooks_empty(self, clean_webhooks) -> None:
        """Test getting webhooks when none registered."""
        assert get_webhooks() == []

    def test_get_webhooks_multiple(self, clean_webhooks) -> None:
        """Test getting multiple webhooks."""
        register_webhook("/hook1", "workflow1", "/path1.yaml")
        register_webhook("/hook2", "workflow2", "/path2.yaml", secret="secret")

        webhooks = get_webhooks()

        assert len(webhooks) == 2
        names = [w["workflow_name"] for w in webhooks]
        assert "workflow1" in names
        assert "workflow2" in names

    def test_get_webhook_specific(self, clean_webhooks) -> None:
        """Test getting a specific workflow's webhook."""
        register_webhook("/hook1", "workflow1", "/path1.yaml")
        register_webhook("/hook2", "workflow2", "/path2.yaml")

        webhook = get_webhook("workflow1")

        assert webhook is not None
        assert webhook["workflow_name"] == "workflow1"
        assert webhook["path"] == "/hook1"

    def test_get_webhook_nonexistent(self, clean_webhooks) -> None:
        """Test getting a non-existent workflow's webhook."""
        webhook = get_webhook("nonexistent")
        assert webhook is None


class TestResolveSecret:
    """Tests for secret resolution."""

    def test_resolve_secret_none(self) -> None:
        """Test resolving None secret."""
        assert _resolve_secret(None) is None

    def test_resolve_secret_plain(self) -> None:
        """Test resolving plain secret."""
        assert _resolve_secret("plain-secret") == "plain-secret"

    def test_resolve_secret_env_var(self) -> None:
        """Test resolving environment variable secret."""
        os.environ["MY_SECRET"] = "secret-from-env"
        try:
            assert _resolve_secret("${MY_SECRET}") == "secret-from-env"
        finally:
            del os.environ["MY_SECRET"]

    def test_resolve_secret_missing_env_var(self) -> None:
        """Test resolving missing environment variable."""
        result = _resolve_secret("${NONEXISTENT_VAR}")
        assert result is None


class TestVerifySignature:
    """Tests for HMAC signature verification."""

    def test_verify_signature_valid(self) -> None:
        """Test valid signature verification."""
        body = b'{"test": "data"}'
        secret = "my-secret"
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        assert _verify_signature(body, secret, expected) is True
        assert _verify_signature(body, secret, f"sha256={expected}") is True

    def test_verify_signature_invalid(self) -> None:
        """Test invalid signature verification."""
        body = b'{"test": "data"}'
        secret = "my-secret"

        assert _verify_signature(body, secret, "invalid-signature") is False


class TestWebhookEndpoint:
    """Tests for webhook HTTP endpoint."""

    def test_webhook_not_found(self, client) -> None:
        """Test 404 for unknown webhook."""
        response = client.post("/hooks/unknown")
        assert response.status_code == 404

    def test_webhook_trigger_success(self, client, clean_webhooks) -> None:
        """Test successful webhook trigger."""
        register_webhook("/test", "test-workflow", "/path/to/workflow.yaml")

        # Mock the background task execution
        with patch("flowpilot.api.webhooks._execute_webhook_workflow"):
            response = client.post(
                "/hooks/test",
                json={"event": "test"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["workflow"] == "test-workflow"
        assert "execution_id" in data

    def test_webhook_with_secret_missing_auth(self, client, clean_webhooks) -> None:
        """Test webhook with secret requires authentication."""
        register_webhook("/secure", "secure-workflow", "/path.yaml", secret="secret123")

        response = client.post("/hooks/secure", json={})

        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_webhook_with_secret_valid(self, client, clean_webhooks) -> None:
        """Test webhook with valid secret header."""
        register_webhook("/secure", "secure-workflow", "/path.yaml", secret="secret123")

        with patch("flowpilot.api.webhooks._execute_webhook_workflow"):
            response = client.post(
                "/hooks/secure",
                json={"event": "test"},
                headers={"X-Webhook-Secret": "secret123"},
            )

        assert response.status_code == 200

    def test_webhook_with_secret_invalid(self, client, clean_webhooks) -> None:
        """Test webhook with invalid secret."""
        register_webhook("/secure", "secure-workflow", "/path.yaml", secret="secret123")

        response = client.post(
            "/hooks/secure",
            json={},
            headers={"X-Webhook-Secret": "wrong-secret"},
        )

        assert response.status_code == 401
        assert "Invalid secret" in response.json()["detail"]

    def test_webhook_with_hmac_signature(self, client, clean_webhooks) -> None:
        """Test webhook with HMAC signature (GitHub style)."""
        secret = "github-secret"
        register_webhook("/github", "github-workflow", "/path.yaml", secret=secret)

        body = b'{"action": "push"}'
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        with patch("flowpilot.api.webhooks._execute_webhook_workflow"):
            response = client.post(
                "/hooks/github",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={signature}",
                },
            )

        assert response.status_code == 200

    def test_webhook_passes_request_data(self, client, clean_webhooks) -> None:
        """Test that webhook passes request data to workflow."""
        register_webhook("/data-test", "data-workflow", "/path.yaml")

        captured_inputs = {}

        def capture_inputs(workflow_name, workflow_path, inputs, execution_id):
            captured_inputs.update(inputs)

        with patch(
            "flowpilot.api.webhooks._execute_webhook_workflow",
            side_effect=capture_inputs,
        ):
            response = client.post(
                "/hooks/data-test?param=value",
                json={"key": "value"},
                headers={"X-Custom-Header": "custom-value"},
            )

        assert response.status_code == 200
        assert "_webhook" in captured_inputs
        webhook_data = captured_inputs["_webhook"]
        assert webhook_data["path"] == "/data-test"
        assert webhook_data["body"] == {"key": "value"}
        assert webhook_data["query"] == {"param": "value"}
        # Headers are lowercase in FastAPI
        assert "x-custom-header" in webhook_data["headers"]


class TestWebhookService:
    """Tests for WebhookService class."""

    def test_service_register(self, clean_webhooks, tmp_path) -> None:
        """Test service registration method."""
        service = WebhookService(tmp_path)

        trigger = WebhookTrigger(
            type="webhook",
            path="/service-hook",
            secret="service-secret",
        )

        webhook_id = service.register("test-workflow", trigger, "/path.yaml")

        assert "webhook:test-workflow" in webhook_id
        assert len(service.get_webhooks()) == 1

    def test_service_unregister(self, clean_webhooks, tmp_path) -> None:
        """Test service unregistration method."""
        service = WebhookService(tmp_path)

        trigger = WebhookTrigger(type="webhook", path="/hook")
        service.register("test-workflow", trigger, "/path.yaml")

        result = service.unregister("test-workflow")

        assert result is True
        assert len(service.get_webhooks()) == 0

    def test_service_get_webhook(self, clean_webhooks, tmp_path) -> None:
        """Test service get_webhook method."""
        service = WebhookService(tmp_path)

        trigger = WebhookTrigger(type="webhook", path="/my-hook")
        service.register("my-workflow", trigger, "/path.yaml")

        webhook = service.get_webhook("my-workflow")

        assert webhook is not None
        assert webhook["path"] == "/my-hook"


class TestSetGlobalRunner:
    """Tests for set_global_webhook_runner function."""

    def test_set_runner(self) -> None:
        """Test setting the global runner."""
        mock_runner = MagicMock()
        set_global_webhook_runner(mock_runner)

        from flowpilot.api import webhooks

        assert webhooks._global_runner == mock_runner

        # Clean up
        set_global_webhook_runner(None)
        assert webhooks._global_runner is None

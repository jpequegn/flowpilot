"""Health check endpoints for FlowPilot API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Check API health status.

    Returns:
        Health status with timestamp.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "flowpilot",
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check() -> dict[str, Any]:
    """Check if the API is ready to serve requests.

    Returns:
        Readiness status.
    """
    return {
        "status": "ready",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/live")
async def liveness_check() -> dict[str, Any]:
    """Check if the API is alive.

    Returns:
        Liveness status.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat(),
    }

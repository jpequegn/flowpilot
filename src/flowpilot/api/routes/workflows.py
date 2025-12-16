"""Workflow CRUD endpoints for FlowPilot API."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from flowpilot.api.dependencies import RequiredRunner, WorkflowsDir
from flowpilot.api.schemas.workflows import (
    WorkflowCreate,
    WorkflowDetail,
    WorkflowListItem,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowUpdate,
    WorkflowValidation,
)
from flowpilot.engine.parser import WorkflowParseError, WorkflowParser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflows")


def _get_workflow_path(workflows_dir: Path, name: str) -> Path:
    """Get the path to a workflow file.

    Args:
        workflows_dir: Base workflows directory.
        name: Workflow name.

    Returns:
        Path to workflow YAML file.
    """
    return workflows_dir / f"{name}.yaml"


def _get_file_timestamps(path: Path) -> tuple[datetime | None, datetime | None]:
    """Get file creation and modification timestamps.

    Args:
        path: Path to file.

    Returns:
        Tuple of (created_at, updated_at) timestamps.
    """
    if not path.exists():
        return None, None

    stat = path.stat()
    # Use ctime as creation time (note: on Unix this is metadata change time)
    created_at = datetime.fromtimestamp(stat.st_ctime, tz=UTC)
    updated_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    return created_at, updated_at


@router.get("", response_model=list[WorkflowListItem])
async def list_workflows(
    workflows_dir: WorkflowsDir,
    search: str | None = Query(None, description="Search workflows by name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> list[WorkflowListItem]:
    """List all workflows.

    Args:
        workflows_dir: Directory containing workflows.
        search: Optional search filter.
        page: Page number for pagination.
        page_size: Number of items per page.

    Returns:
        List of workflow summaries.
    """
    parser = WorkflowParser()
    workflows: list[WorkflowListItem] = []

    for yaml_file in sorted(workflows_dir.glob("*.yaml")):
        try:
            workflow = parser.parse_file(yaml_file)

            # Apply search filter
            if search and search.lower() not in workflow.name.lower():
                continue

            created_at, updated_at = _get_file_timestamps(yaml_file)
            workflows.append(
                WorkflowListItem(
                    name=workflow.name,
                    description=workflow.description,
                    version=workflow.version,
                    path=str(yaml_file),
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
        except WorkflowParseError:
            # Skip invalid workflow files
            logger.warning(f"Skipping invalid workflow file: {yaml_file}")
            continue

    # Apply pagination
    start = (page - 1) * page_size
    end = start + page_size
    return workflows[start:end]


@router.post("", response_model=WorkflowDetail, status_code=201)
async def create_workflow(
    workflows_dir: WorkflowsDir,
    workflow_data: WorkflowCreate,
) -> WorkflowDetail:
    """Create a new workflow.

    Args:
        workflows_dir: Directory containing workflows.
        workflow_data: Workflow creation data.

    Returns:
        Created workflow details.

    Raises:
        HTTPException: If workflow already exists or YAML is invalid.
    """
    workflow_path = _get_workflow_path(workflows_dir, workflow_data.name)

    # Check if workflow already exists
    if workflow_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Workflow '{workflow_data.name}' already exists",
        )

    # Validate the YAML content
    parser = WorkflowParser()
    try:
        workflow = parser.parse_string(workflow_data.content)
    except WorkflowParseError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workflow YAML: {e}",
        ) from e

    # Verify the name in YAML matches the requested name
    if workflow.name != workflow_data.name:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow name in YAML ('{workflow.name}') does not match "
            f"requested name ('{workflow_data.name}')",
        )

    # Write the workflow file
    workflow_path.write_text(workflow_data.content)

    created_at, updated_at = _get_file_timestamps(workflow_path)
    return WorkflowDetail(
        name=workflow.name,
        description=workflow.description,
        version=workflow.version,
        path=str(workflow_path),
        content=workflow_data.content,
        triggers=[t.model_dump() for t in workflow.triggers],
        inputs={k: v.model_dump() for k, v in workflow.inputs.items()},
        node_count=len(workflow.nodes),
        created_at=created_at,
        updated_at=updated_at,
    )


@router.get("/{name}", response_model=WorkflowDetail)
async def get_workflow(
    name: str,
    workflows_dir: WorkflowsDir,
) -> WorkflowDetail:
    """Get workflow details.

    Args:
        name: Workflow name.
        workflows_dir: Directory containing workflows.

    Returns:
        Workflow details.

    Raises:
        HTTPException: If workflow not found.
    """
    workflow_path = _get_workflow_path(workflows_dir, name)

    if not workflow_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{name}' not found",
        )

    content = workflow_path.read_text()
    parser = WorkflowParser()

    try:
        workflow = parser.parse_string(content)
    except WorkflowParseError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing workflow: {e}",
        ) from e

    created_at, updated_at = _get_file_timestamps(workflow_path)
    return WorkflowDetail(
        name=workflow.name,
        description=workflow.description,
        version=workflow.version,
        path=str(workflow_path),
        content=content,
        triggers=[t.model_dump() for t in workflow.triggers],
        inputs={k: v.model_dump() for k, v in workflow.inputs.items()},
        node_count=len(workflow.nodes),
        created_at=created_at,
        updated_at=updated_at,
    )


@router.put("/{name}", response_model=WorkflowDetail)
async def update_workflow(
    name: str,
    workflows_dir: WorkflowsDir,
    workflow_data: WorkflowUpdate,
) -> WorkflowDetail:
    """Update an existing workflow.

    Args:
        name: Workflow name.
        workflows_dir: Directory containing workflows.
        workflow_data: Updated workflow data.

    Returns:
        Updated workflow details.

    Raises:
        HTTPException: If workflow not found or YAML is invalid.
    """
    workflow_path = _get_workflow_path(workflows_dir, name)

    if not workflow_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{name}' not found",
        )

    # Validate the YAML content
    parser = WorkflowParser()
    try:
        workflow = parser.parse_string(workflow_data.content)
    except WorkflowParseError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workflow YAML: {e}",
        ) from e

    # Verify the name in YAML matches the URL name
    if workflow.name != name:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow name in YAML ('{workflow.name}') does not match URL name ('{name}')",
        )

    # Write the updated workflow file
    workflow_path.write_text(workflow_data.content)

    created_at, updated_at = _get_file_timestamps(workflow_path)
    return WorkflowDetail(
        name=workflow.name,
        description=workflow.description,
        version=workflow.version,
        path=str(workflow_path),
        content=workflow_data.content,
        triggers=[t.model_dump() for t in workflow.triggers],
        inputs={k: v.model_dump() for k, v in workflow.inputs.items()},
        node_count=len(workflow.nodes),
        created_at=created_at,
        updated_at=updated_at,
    )


@router.delete("/{name}", status_code=204)
async def delete_workflow(
    name: str,
    workflows_dir: WorkflowsDir,
) -> None:
    """Delete a workflow.

    Args:
        name: Workflow name.
        workflows_dir: Directory containing workflows.

    Raises:
        HTTPException: If workflow not found.
    """
    workflow_path = _get_workflow_path(workflows_dir, name)

    if not workflow_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{name}' not found",
        )

    workflow_path.unlink()


@router.get("/{name}/validate", response_model=WorkflowValidation)
async def validate_workflow(
    name: str,
    workflows_dir: WorkflowsDir,
) -> WorkflowValidation:
    """Validate a workflow.

    Args:
        name: Workflow name.
        workflows_dir: Directory containing workflows.

    Returns:
        Validation result with errors and warnings.

    Raises:
        HTTPException: If workflow not found.
    """
    workflow_path = _get_workflow_path(workflows_dir, name)

    if not workflow_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{name}' not found",
        )

    content = workflow_path.read_text()
    parser = WorkflowParser()

    try:
        workflow = parser.parse_string(content)
        warnings = parser.validate(workflow)
        return WorkflowValidation(valid=True, errors=[], warnings=warnings)
    except WorkflowParseError as e:
        return WorkflowValidation(valid=False, errors=e.errors, warnings=[])


@router.post("/{name}/run", response_model=WorkflowRunResponse)
async def run_workflow(
    name: str,
    workflows_dir: WorkflowsDir,
    runner: RequiredRunner,
    background_tasks: BackgroundTasks,
    run_request: WorkflowRunRequest | None = None,
) -> WorkflowRunResponse:
    """Execute a workflow.

    Args:
        name: Workflow name.
        workflows_dir: Directory containing workflows.
        runner: Workflow runner instance.
        background_tasks: FastAPI background tasks.
        run_request: Optional run parameters.

    Returns:
        Execution information with ID.

    Raises:
        HTTPException: If workflow not found.
    """
    workflow_path = _get_workflow_path(workflows_dir, name)

    if not workflow_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{name}' not found",
        )

    parser = WorkflowParser()
    try:
        workflow = parser.parse_file(workflow_path)
    except WorkflowParseError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing workflow: {e}",
        ) from e

    # Generate execution ID
    execution_id = str(uuid.uuid4())
    inputs = run_request.inputs if run_request else {}

    # Execute in background
    background_tasks.add_task(
        _execute_workflow,
        runner=runner,
        workflow=workflow,
        inputs=inputs,
        execution_id=execution_id,
        workflow_path=str(workflow_path),
    )

    logger.info(f"Started workflow '{name}' (execution_id={execution_id[:8]}...)")

    return WorkflowRunResponse(
        execution_id=execution_id,
        workflow=name,
        status="accepted",
    )


async def _execute_workflow(
    runner: Any,
    workflow: Any,
    inputs: dict[str, Any],
    execution_id: str,
    workflow_path: str,
) -> None:
    """Execute a workflow in the background.

    Args:
        runner: Workflow runner instance.
        workflow: Parsed workflow.
        inputs: Input parameters.
        execution_id: Execution ID.
        workflow_path: Path to workflow file.
    """
    try:
        await runner.run(
            workflow,
            inputs=inputs,
            execution_id=execution_id,
            workflow_path=workflow_path,
            trigger_type="api",
        )
        logger.info(f"Completed workflow execution {execution_id[:8]}...")
    except Exception as e:
        logger.exception(f"Failed workflow execution {execution_id[:8]}...: {e}")

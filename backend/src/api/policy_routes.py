from __future__ import annotations

"""REST endpoints for policy CRUD operations and file download.

Admin-protected routes for uploading, updating, deleting policies,
plus public read / download endpoints.
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from backend.config.settings import settings
from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.services.policy_service import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    create_policy,
    delete_policy,
    get_policy,
    get_policy_path,
    list_policies,
    update_policy,
)

logger = logging.getLogger("hr_ops.policy_routes")
router = APIRouter(prefix="/policies", tags=["policies"])


def _admin_required(correlation_id: str):
    """Check if the configured app role is 'admin'; return an error response if not."""
    role = os.environ.get("APP_ROLE") or settings.roles_config.get("app_role", "admin")
    if role != "admin":
        return error_response(
            message="Admin access required",
            correlation_id=correlation_id,
            status_code=403,
        )
    return None


@router.get("")
async def api_list_policies(request: Request):
    """List all policy files with their metadata.

    ---
    Request:
        GET /policies

    Response 200:
        {
          "success": true,
          "data": {
            "policies": [
              {
                "id": "leave_policy.md",
                "filename": "leave_policy.md",
                "title": "Leave Policy",
                "content_type": "text/markdown",
                "file_size": 2048,
                "updated_at": "2026-06-12T10:00:00"
              }
            ]
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    policies = list_policies()
    return success_response(data={"policies": policies}, correlation_id=correlation_id)


@router.get("/{policy_id}")
async def api_get_policy(policy_id: str, request: Request):
    """Retrieve a single policy's metadata and full text content.

    ---
    Request:
        GET /policies/leave_policy.md

    Response 200:
        {
          "success": true,
          "data": {
            "id": "leave_policy.md",
            "filename": "leave_policy.md",
            "title": "Leave Policy",
            "content": "# Leave Policy\\n\\nEmployees are entitled to 15 days...",
            "content_type": "text/markdown",
            "file_size": 2048,
            "updated_at": "2026-06-12T10:00:00"
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Policy not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    policy = get_policy(policy_id)
    if not policy:
        return error_response(
            message="Policy not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(data=policy, correlation_id=correlation_id)


@router.get("/{policy_id}/download")
async def api_download_policy(policy_id: str, request: Request):
    """Download the raw policy file as a binary stream.

    ---
    Request:
        GET /policies/leave_policy.md/download

    Response 200: Binary file stream
        Content-Type: application/octet-stream
        Content-Disposition: attachment; filename="leave_policy.md"

    Response 404:
        {"success": false, "message": "Policy not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    path = get_policy_path(policy_id)
    if not path:
        return error_response(
            message="Policy not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return FileResponse(
        path=str(path), filename=path.name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.post("/upload")
async def api_upload_policy(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(default=""),
):
    """Upload a new policy file (admin-only). Validates extension and file size.

    ---
    Request:
        POST /policies/upload
        Content-Type: multipart/form-data
        file: <binary>, title: "Leave Policy"

    Response 200:
        {
          "success": true,
          "data": {
            "id": "leave_policy.md",
            "filename": "leave_policy.md",
            "title": "Leave Policy",
            "content_type": "text/markdown",
            "file_size": 2048,
            "updated_at": "2026-06-13T00:00:00"
          },
          "message": "Policy created",
          "correlation_id": "abc123"
        }

    Response 400:
        {"success": false, "message": "Unsupported file type '.exe'. Allowed: .pdf, .md, .txt", "correlation_id": "abc123"}

    Response 403:
        {"success": false, "message": "Admin access required", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)

    denied = _admin_required(correlation_id)
    if denied:
        return denied

    if not file.filename:
        return error_response(
            message="No file provided",
            correlation_id=correlation_id,
            status_code=400,
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return error_response(
            message=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            correlation_id=correlation_id,
            status_code=400,
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return error_response(
            message=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)} MB",
            correlation_id=correlation_id,
            status_code=400,
        )

    try:
        policy = create_policy(file.filename, content, title=title or None)
        return success_response(data=policy, correlation_id=correlation_id, message="Policy created")
    except ValueError as e:
        return error_response(message=str(e), correlation_id=correlation_id, status_code=400)


@router.put("/{policy_id}")
async def api_update_policy(policy_id: str, body: dict, request: Request):
    """Update a policy's title (admin-only).

    ---
    Request:
        PUT /policies/leave_policy.md
        {"title": "Updated Leave Policy"}

    Response 200:
        {
          "success": true,
          "data": {
            "id": "leave_policy.md",
            "filename": "leave_policy.md",
            "title": "Updated Leave Policy",
            "content_type": "text/markdown",
            "file_size": 2048,
            "updated_at": "2026-06-13T00:01:00"
          },
          "message": "Policy updated",
          "correlation_id": "abc123"
        }

    Response 403:
        {"success": false, "message": "Admin access required", "correlation_id": "abc123"}

    Response 404:
        {"success": false, "message": "Policy not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    denied = _admin_required(correlation_id)
    if denied:
        return denied
    title = body.get("title")
    if not title or not title.strip():
        return error_response(
            message="Title is required",
            correlation_id=correlation_id,
            status_code=400,
        )
    policy = update_policy(policy_id, title=title.strip())
    if not policy:
        return error_response(
            message="Policy not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(data=policy, correlation_id=correlation_id, message="Policy updated")


@router.delete("/{policy_id}")
async def api_delete_policy(policy_id: str, request: Request):
    """Delete a policy file (admin-only).

    ---
    Request:
        DELETE /policies/leave_policy.md

    Response 200:
        {
          "success": true,
          "data": {"id": "leave_policy.md"},
          "message": "Policy deleted",
          "correlation_id": "abc123"
        }

    Response 403:
        {"success": false, "message": "Admin access required", "correlation_id": "abc123"}

    Response 404:
        {"success": false, "message": "Policy not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    denied = _admin_required(correlation_id)
    if denied:
        return denied
    deleted = delete_policy(policy_id)
    if not deleted:
        return error_response(
            message="Policy not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(data={"id": policy_id}, correlation_id=correlation_id, message="Policy deleted")

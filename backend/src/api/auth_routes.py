"""REST endpoints for authentication — login with role + password."""

import logging

from fastapi import APIRouter, Request

from backend.src.core.response import error_response, get_correlation_id, success_response
from backend.src.utils.auth import VALID_ROLES, create_token

logger = logging.getLogger("hr_ops.auth_routes")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(payload: dict, request: Request | None = None):
    """Authenticate a user by role and password.

    For now, password must equal the role name (e.g., role='admin', password='admin').

    ---
    Request:
        POST /auth/login
        {
          "role": "admin",
          "password": "admin"
        }

    For employee role, an employee_id is also required:
        {
          "role": "employee",
          "password": "employee",
          "employee_id": "1"
        }

    Response 200:
        {
          "success": true,
          "data": {
            "token": "eyJ...",
            "role": "admin",
            "employee_id": ""
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    role = (payload.get("role") or "").strip().lower()
    password = payload.get("password", "")
    employee_id = (payload.get("employee_id") or "").strip()

    if role not in VALID_ROLES:
        return error_response(
            message=f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}",
            correlation_id=correlation_id,
            status_code=400,
        )

    if password != role:
        return error_response(
            message="Invalid password",
            correlation_id=correlation_id,
            status_code=401,
        )

    if role == "employee" and not employee_id:
        return error_response(
            message="employee_id is required for employee role",
            correlation_id=correlation_id,
            status_code=400,
        )

    token = create_token(role, employee_id)
    return success_response(
        data={"token": token, "role": role, "employee_id": employee_id},
        correlation_id=correlation_id,
    )

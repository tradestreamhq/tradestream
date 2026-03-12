"""
Standardized REST API response formats for RMM Level 2 compliance.

All APIs return consistent JSON following these patterns:
- Single resource: {"data": {"id": "...", "type": "...", "attributes": {...}}}
- Collection: {"data": [...], "meta": {"total": N, "limit": N, "offset": N}}
- Error: {"error": {"code": "...", "message": "...", "details": [...]}}
"""

from typing import Any, Dict, List, Optional, Sequence

from fastapi import Request
from fastapi.responses import JSONResponse


def success_response(
    data: Any,
    resource_type: str,
    resource_id: Optional[str] = None,
    status_code: int = 200,
) -> JSONResponse:
    """Wrap a single resource in the standard envelope."""
    body: Dict[str, Any] = {
        "data": {
            "type": resource_type,
            "attributes": data,
        }
    }
    if resource_id is not None:
        body["data"]["id"] = resource_id
    return JSONResponse(content=body, status_code=status_code)


def collection_response(
    items: Sequence[Dict[str, Any]],
    resource_type: str,
    total: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    """Wrap a list of resources in the standard envelope with pagination meta."""
    data = []
    for item in items:
        entry: Dict[str, Any] = {
            "type": resource_type,
            "attributes": item,
        }
        if "id" in item:
            entry["id"] = str(item["id"])
        data.append(entry)

    body: Dict[str, Any] = {
        "data": data,
        "meta": {
            "total": total if total is not None else len(items),
            "limit": limit,
            "offset": offset,
        },
    }
    return JSONResponse(content=body, status_code=200)


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: Optional[List[Dict[str, str]]] = None,
) -> JSONResponse:
    """Return a standardized error response."""
    body: Dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(content=body, status_code=status_code)


def not_found(resource: str, identifier: str) -> JSONResponse:
    """Convenience helper for 404 responses."""
    return error_response(
        code="NOT_FOUND",
        message=f"{resource} '{identifier}' not found",
        status_code=404,
    )


def validation_error(
    message: str, details: Optional[List[Dict[str, str]]] = None
) -> JSONResponse:
    """Convenience helper for 422 responses."""
    return error_response(
        code="VALIDATION_ERROR",
        message=message,
        status_code=422,
        details=details,
    )


def conflict(message: str) -> JSONResponse:
    """Convenience helper for 409 responses."""
    return error_response(
        code="CONFLICT",
        message=message,
        status_code=409,
    )


def server_error(message: str = "Internal server error") -> JSONResponse:
    """Convenience helper for 500 responses."""
    return error_response(
        code="SERVER_ERROR",
        message=message,
        status_code=500,
    )

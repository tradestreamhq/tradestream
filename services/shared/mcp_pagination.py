"""Pagination helpers for MCP servers.

Provides standardized pagination response formatting per the MCP servers spec.
"""

from typing import Any


def paginated_response(
    items: list[Any],
    offset: int,
    limit: int,
    total: int,
) -> dict[str, Any]:
    """Build a paginated response per spec.

    Args:
        items: The page of results.
        offset: Current offset.
        limit: Page size.
        total: Total count of matching items.

    Returns:
        Dict with items and pagination metadata.
    """
    return {
        "items": items,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": (offset + limit) < total,
        },
    }


def clamp_pagination(
    offset: int,
    limit: int,
    max_limit: int = 100,
) -> tuple[int, int]:
    """Clamp offset and limit to valid ranges.

    Args:
        offset: Requested offset (clamped to >= 0).
        limit: Requested limit (clamped to 1..max_limit).
        max_limit: Maximum allowed limit.

    Returns:
        Tuple of (clamped_offset, clamped_limit).
    """
    return max(0, offset), max(1, min(limit, max_limit))

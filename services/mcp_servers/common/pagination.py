"""Pagination utilities for MCP servers."""

from typing import Any, Dict, List, TypeVar
from dataclasses import dataclass

T = TypeVar("T")


@dataclass
class PaginationResult:
    """Result of a paginated query."""

    items: List[Any]
    offset: int
    limit: int
    total: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "items": self.items,
            "pagination": {
                "offset": self.offset,
                "limit": self.limit,
                "total": self.total,
                "has_more": self.has_more,
            },
        }


def paginate(
    items: List[T],
    offset: int = 0,
    limit: int = 10,
    max_limit: int = 100,
) -> PaginationResult:
    """Apply pagination to a list of items.

    Args:
        items: Full list of items
        offset: Number of items to skip
        limit: Maximum number of items to return
        max_limit: Maximum allowed limit value

    Returns:
        PaginationResult with paginated items and metadata
    """
    # Enforce limits
    offset = max(0, offset)
    limit = max(1, min(limit, max_limit))

    total = len(items)
    paginated_items = items[offset : offset + limit]

    return PaginationResult(
        items=paginated_items,
        offset=offset,
        limit=limit,
        total=total,
    )


def sql_pagination(offset: int = 0, limit: int = 10, max_limit: int = 100) -> str:
    """Generate SQL LIMIT/OFFSET clause.

    Args:
        offset: Number of rows to skip
        limit: Maximum number of rows to return
        max_limit: Maximum allowed limit value

    Returns:
        SQL string like "LIMIT 10 OFFSET 0"
    """
    offset = max(0, offset)
    limit = max(1, min(limit, max_limit))
    return f"LIMIT {limit} OFFSET {offset}"


def count_query(base_query: str) -> str:
    """Wrap a base query to get total count.

    Args:
        base_query: The SELECT query (without LIMIT/OFFSET)

    Returns:
        A query that returns the total count
    """
    return f"SELECT COUNT(*) FROM ({base_query}) AS count_subquery"

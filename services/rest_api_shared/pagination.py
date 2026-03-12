"""
Pagination helpers for REST API list endpoints.
"""

from typing import Optional

from fastapi import Query


class PaginationParams:
    """Common pagination query parameters."""

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=1000, description="Maximum items to return"),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
    ):
        self.limit = limit
        self.offset = offset

"""Priority queue for rate-limited requests."""

import heapq
from typing import Optional

from services.rate_limiter.models import RateLimitedRequest


class PriorityRequestQueue:
    """A priority queue that orders requests by priority level.

    Market orders are processed first, then limit orders, then data requests.
    Within the same priority, requests are ordered by creation time (FIFO).
    """

    def __init__(self):
        self._heap: list[tuple[int, float, RateLimitedRequest]] = []
        self._counter = 0  # Tiebreaker for stable ordering

    def push(self, request: RateLimitedRequest) -> None:
        """Add a request to the queue."""
        heapq.heappush(self._heap, (request.priority, self._counter, request))
        self._counter += 1

    def pop(self) -> Optional[RateLimitedRequest]:
        """Remove and return the highest-priority request, or None if empty."""
        if not self._heap:
            return None
        _, _, request = heapq.heappop(self._heap)
        return request

    def peek(self) -> Optional[RateLimitedRequest]:
        """Return the highest-priority request without removing it."""
        if not self._heap:
            return None
        _, _, request = self._heap[0]
        return request

    @property
    def size(self) -> int:
        return len(self._heap)

    @property
    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def clear(self) -> None:
        """Remove all requests from the queue."""
        self._heap.clear()
        self._counter = 0

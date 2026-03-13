"""CORS middleware configuration for FastAPI.

Wraps Starlette's built-in ``CORSMiddleware`` with project-sensible defaults
and an easy way to configure allowed origins.
"""

from typing import Optional, Sequence

from starlette.middleware.cors import CORSMiddleware


# Default allowed origins (restrict in production via env or config).
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
]


def fastapi_cors(
    app,
    allowed_origins: Optional[Sequence[str]] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[Sequence[str]] = None,
    allow_headers: Optional[Sequence[str]] = None,
):
    """Add CORS middleware to a FastAPI/Starlette application.

    Args:
        app: The FastAPI or Starlette application.
        allowed_origins: List of allowed origin URLs.
        allow_credentials: Whether to allow credentials (cookies, auth headers).
        allow_methods: Allowed HTTP methods.  Defaults to all.
        allow_headers: Allowed headers.  Defaults to all.
    """
    origins = list(allowed_origins) if allowed_origins else DEFAULT_ALLOWED_ORIGINS
    methods = list(allow_methods) if allow_methods else ["*"]
    headers = list(allow_headers) if allow_headers else ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=methods,
        allow_headers=headers,
    )

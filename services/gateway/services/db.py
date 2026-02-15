"""Database connection management using asyncpg."""

import asyncpg
from typing import Optional

from ..config import settings

# Global connection pool
pool: Optional[asyncpg.Pool] = None


async def init_db():
    """Initialize database connection pool."""
    global pool
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=settings.DATABASE_POOL_SIZE,
    )


async def close_db():
    """Close database connection pool."""
    global pool
    if pool:
        await pool.close()
        pool = None


async def get_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return pool

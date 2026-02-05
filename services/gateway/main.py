"""TradeStream Gateway API - Main application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import health
from .middleware.error_handler import add_error_handlers
from .services.db import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="TradeStream Gateway API",
    description="Unified API for the TradeStream trading signal platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handlers
add_error_handlers(app)

# Routers - health always included
app.include_router(health.router)

# Additional routers will be added as they are implemented:
# app.include_router(auth.router)
# app.include_router(signals.router)
# app.include_router(users.router)
# app.include_router(providers.router)
# app.include_router(social.router)
# app.include_router(leaderboards.router)
# app.include_router(achievements.router)
# app.include_router(referrals.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

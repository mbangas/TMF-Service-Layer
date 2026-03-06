"""TMF Service Layer — FastAPI application entry-point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.catalog.api.router import router as catalog_router
from src.config import settings
from src.inventory.api.router import router as inventory_router
from src.order.api.router import router as order_router
from src.provisioning.api.router import router as provisioning_router
from src.qualification.api.router import router as qualification_router
from src.shared.db.session import engine
from src.shared.events.bus import EventBus
from src.shared.events.schemas import TMFEvent


# ── Lifespan (DB pool management) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the SQLAlchemy async engine lifecycle.

    Opens the connection pool on startup and disposes it cleanly on shutdown.
    """
    # Startup: pool is created lazily by SQLAlchemy; nothing explicit needed
    yield
    # Shutdown: dispose the engine / return connections to the OS
    await engine.dispose()


# ── FastAPI instance ───────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "TMForum ODA-compliant Service Layer REST APIs.\n\n"
        "Implements the full service lifecycle: catalog, orders, inventory, "
        "provisioning, assurance, testing, and commercial support.\n\n"
        "Reference: [TM Forum Open APIs](https://www.tmforum.org/open-apis/)"
    ),
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Result-Count"],
)

# ── Domain routers ─────────────────────────────────────────────────────────────
app.include_router(catalog_router)
app.include_router(order_router)
app.include_router(inventory_router)
app.include_router(provisioning_router)
app.include_router(qualification_router)

# Future routers (placeholder — uncomment as modules are implemented):
#
# from src.assurance.api.router import router as assurance_router
# app.include_router(assurance_router)
#
# from src.testing.api.router import router as testing_router
# app.include_router(testing_router)
#
# from src.problem.api.router import router as problem_router
# app.include_router(problem_router)
#
# from src.commercial.api.router import router as commercial_router
# app.include_router(commercial_router)


# ── Static frontend (served at /ui) ───────────────────────────────────────────
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")


# ── Dev events endpoint ───────────────────────────────────────────────────────
@app.get("/events", tags=["System"], summary="Recent TMF events (dev only)")
async def list_events(limit: int = 100) -> list[TMFEvent]:
    """Return recent TMF lifecycle events from the in-memory event bus.

    Only available when ``APP_ENV=development``.
    """
    from fastapi import HTTPException  # noqa: PLC0415

    if settings.app_env != "development":
        raise HTTPException(status_code=404, detail="Not found.")
    return EventBus.get_events(limit=limit)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"], summary="Health check")
async def health_check() -> JSONResponse:
    """Return the application health status."""
    return JSONResponse(
        content={
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
        }
    )

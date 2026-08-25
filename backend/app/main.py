"""Production FastAPI application entry point for PipeVision backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.analytics import router as analytics_router
from backend.app.api.health import router as health_router
from backend.app.api.missions import router as missions_router
from backend.app.api.robots import router as robots_router
from backend.app.api.telemetry import router as telemetry_router
from backend.app.api.video import router as video_router
from backend.app.config import get_settings
from backend.app.db import close_db, init_db
from backend.app.logging_config import setup_logging
from backend.app.middleware import CorrelationIdMiddleware
from backend.app.realtime import telemetry_broadcaster
from backend.app.services.video.sewer_classifier import reset_sewer_classifier_engine

logger = logging.getLogger("pipevision.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Production lifespan context manager replacing deprecated on_event handlers."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info("Initializing PipeVision backend [environment=%s, debug=%s]", settings.environment, settings.debug)

    settings.validate_environment()
    init_db()
    logger.info("Database and storage initialized successfully.")

    yield

    logger.info("Shutting down PipeVision backend resources...")
    close_db()
    reset_sewer_classifier_engine()
    logger.info("Shutdown complete.")


settings = get_settings()

app = FastAPI(
    title="PipeVision API",
    version="0.2.0",
    description="Robot-agnostic pipeline inspection, 3D reconstruction, and graph analytics backend.",
    docs_url="/docs" if not settings.is_production or settings.debug else None,
    redoc_url="/redoc" if not settings.is_production or settings.debug else None,
    lifespan=lifespan,
)

# Custom Middleware
app.add_middleware(CorrelationIdMiddleware)

if "*" not in settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    cid = getattr(request.state, "correlation_id", "-")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "detail": exc.detail,
            "status_code": exc.status_code,
            "correlation_id": cid,
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    cid = getattr(request.state, "correlation_id", "-")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "detail": exc.errors(),
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "correlation_id": cid,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    cid = getattr(request.state, "correlation_id", "-")
    logger.error("Unhandled exception processing request %s %s [correlation_id=%s]: %s", request.method, request.url.path, cid, exc, exc_info=exc)

    detail = str(exc) if not settings.is_production else "Internal server error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "detail": detail,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "correlation_id": cid,
        },
    )


# Routers
app.include_router(health_router)
app.include_router(video_router, prefix="/api/v1")
app.include_router(robots_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(missions_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")


@app.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    await telemetry_broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        telemetry_broadcaster.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket exception: %s", exc)
        telemetry_broadcaster.disconnect(websocket)

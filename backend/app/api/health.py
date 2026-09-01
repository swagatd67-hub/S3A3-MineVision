"""Health, liveness, readiness, and operational metrics API endpoints for production deployment."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import check_database_connection, get_db
from backend.app.models import Mission, Telemetry
from backend.app.services.video.sewer_classifier import get_sewer_classifier_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_START_TIME = time.time()


@router.get("/health")
@router.get("/health/live")
def liveness_check() -> dict:
    """Liveness probe: verifies process health and responsiveness."""
    settings = get_settings()
    return {
        "status": "live",
        "service": "pipevision-api",
        "version": "0.2.0",
        "environment": settings.environment,
        "runtime_mode": (
            "HARDWARE"
            if settings.robot_hardware_enabled
            and settings.robot_transport_type not in {"sim", "simulator"}
            else "SIMULATOR"
        ),
    }


@router.get("/health/ready")
def readiness_check(response: Response) -> dict:
    """Readiness probe: checks database connectivity, AI model readiness, and media storage accessibility."""
    settings = get_settings()

    db_ok, db_msg = check_database_connection()

    # AI Model readiness
    ai_status = "ready"
    ai_msg = "sewer_engine_ready"
    ckpt_exists = settings.sewer_checkpoint_path.exists()

    if not ckpt_exists and not settings.allow_null_sewer_engine:
        ai_status = "not_ready"
        ai_msg = "missing_production_checkpoint"
    else:
        try:
            engine = get_sewer_classifier_engine()
            ai_msg = engine.model_version
        except (RuntimeError, ValueError, OSError) as exc:
            ai_status = "not_ready"
            ai_msg = f"model_error: {exc}"

    # Storage readiness
    storage_ok = True
    storage_msg = "storage_accessible"
    for path in (settings.media_storage_root, settings.media_import_root):
        if not path.exists():
            storage_ok = False
            storage_msg = f"directory_missing: {path.name}"
            break

    components = {
        "database": {"status": "ready" if db_ok else "not_ready", "detail": db_msg},
        "ai_model": {"status": ai_status, "detail": ai_msg, "checkpoint_exists": ckpt_exists},
        "storage": {"status": "ready" if storage_ok else "not_ready", "detail": storage_msg},
    }

    all_ready = db_ok and (ai_status == "ready") and storage_ok

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if all_ready else "not_ready",
        "service": "pipevision-api",
        "version": "0.2.0",
        "environment": settings.environment,
        "components": components,
    }


@router.get("/metrics")
def operational_metrics(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Lightweight operational metrics endpoint."""
    settings = get_settings()
    uptime_s = round(time.time() - _START_TIME, 2)

    db_ok, _ = check_database_connection()
    mission_count = 0
    telemetry_count = 0

    if db_ok:
        try:
            mission_count = db.scalar(select(func.count(Mission.mission_id))) or 0
            telemetry_count = db.scalar(select(func.count(Telemetry.id))) or 0
        except (SQLAlchemyError, OSError) as exc:
            logger.debug("Failed to query DB metrics: %s", exc)

    try:
        engine = get_sewer_classifier_engine()
        engine_version = engine.model_version
    except (RuntimeError, ValueError, OSError):
        engine_version = "unavailable"

    return {
        "service": "pipevision-api",
        "version": "0.2.0",
        "environment": settings.environment,
        "uptime_s": uptime_s,
        "database_connected": db_ok,
        "total_missions": mission_count,
        "total_telemetry_records": telemetry_count,
        "ai_engine_version": engine_version,
    }

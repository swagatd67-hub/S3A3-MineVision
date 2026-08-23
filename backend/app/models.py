from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Robot(Base):
    __tablename__ = "robots"

    robot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    firmware_version: Mapped[str] = mapped_column(String(64), default="dev")
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Mission(Base):
    __tablename__ = "missions"

    mission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    robot_id: Mapped[str] = mapped_column(String(64), index=True)
    objective: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    robot_id: Mapped[str] = mapped_column(String(64), index=True)
    mission_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("missions.mission_id"), index=True, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_diameter_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="IDLE")
    imu: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pressure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    water: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class InspectionObservationRow(Base):
    __tablename__ = "inspection_observations"

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("missions.mission_id"), index=True
    )
    frame_index: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    class_code: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    localization_quality: Mapped[str] = mapped_column(
        String(32), default="UNAVAILABLE"
    )
    model_name: Mapped[str] = mapped_column(String(64), default="unknown")
    model_version: Mapped[str] = mapped_column(String(32), default="v1")
    box: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    robot_pose: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

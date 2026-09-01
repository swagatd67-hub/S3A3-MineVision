"""Typed production configuration and environment validation layer for PipeVision."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

EnvironmentType = Literal["development", "test", "production"]
CameraSourceType = Literal["simulator", "esp32cam"]


class ConfigurationError(ValueError):
    """Raised when application configuration validation fails."""


class Settings(BaseModel):
    """Canonical typed configuration for PipeVision backend."""

    environment: EnvironmentType = Field(default="development")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)

    # Database Settings
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/pipevision"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: float = Field(default=30.0, gt=0)
    db_pool_recycle: int = Field(default=1800, ge=60)

    # AI Model Settings
    sewer_checkpoint_path: Path = Field(
        default=Path("experiments/sewer/E009/best.pt")
    )
    sewer_thresholds_path: Path = Field(
        default=Path("experiments/sewer/E009/thresholds.json")
    )
    allow_null_sewer_engine: bool = Field(default=False)
    yolo_model_path: str = Field(default="yolo11n.pt")
    yolo_confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)

    # Media & File System Paths
    media_import_root: Path = Field(default=Path("data/import"))
    media_storage_root: Path = Field(default=Path("data/frames"))

    # Logging & Security
    log_level: str = Field(default="INFO")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])
    secret_key: str | None = Field(default=None)

    # Hardware Integration Settings
    robot_transport_type: str = Field(default="simulator")
    robot_host: str = Field(default="192.168.1.100")
    robot_port: int = Field(default=5000, ge=1, le=65535)
    robot_serial_port: str = Field(default="/dev/ttyUSB0")
    robot_baudrate: int = Field(default=115200, ge=1200, le=4000000)
    # When True, RPi transport logs commands but never opens a real socket.
    # Defaults to True so developers can work safely without physical hardware.
    robot_dry_run: bool = Field(default=True)
    robot_hardware_enabled: bool = Field(default=False)
    # GPIO is opt-in; servo pin/limit configuration is JSON so each deployment
    # can provide its own board wiring and calibration.
    robot_gpio_enabled: bool = Field(default=False)
    robot_servo_config_json: str | None = Field(default=None)
    robot_pico_uart_enabled: bool = Field(default=False)
    robot_pico_uart_port: str = Field(default="")
    robot_pico_uart_baudrate: int = Field(default=115200, ge=1200, le=4000000)
    robot_pico_uart_timeout_s: float = Field(default=1.0, gt=0)
    robot_mpu6050_enabled: bool = Field(default=False)
    robot_mpu6050_i2c_bus: int = Field(default=1, ge=0)
    robot_mpu6050_i2c_address: int = Field(default=0x68, ge=0x03, le=0x77)
    robot_mpu6050_accelerometer_scale_g: int = Field(default=2)
    robot_mpu6050_gyroscope_scale_dps: int = Field(default=250)

    # Video source selection. Simulator is deliberately the safe default.
    camera_source_type: CameraSourceType = Field(default="simulator")
    esp32_cam_url: str | None = Field(default=None)
    esp32_cam_timeout_s: float = Field(default=3.0, gt=0)

    # Resource & Processing Limits
    max_upload_size_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)
    max_batch_image_count: int = Field(default=500, ge=1, le=5000)
    max_batch_video_size_bytes: int = Field(
        default=500 * 1024 * 1024, ge=1024
    )
    websocket_heartbeat_interval_s: float = Field(default=30.0, gt=0)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    def validate_environment(self) -> None:
        """Validate production configuration strictness rules."""
        if self.robot_pico_uart_enabled and not self.robot_pico_uart_port.strip():
            raise ConfigurationError(
                "ROBOT_PICO_UART_PORT must be configured when Pico UART is enabled."
            )

        if self.camera_source_type == "esp32cam":
            if not self.esp32_cam_url:
                raise ConfigurationError(
                    "ESP32_CAM_URL must be configured when CAMERA_SOURCE_TYPE=esp32cam."
                )
            parsed_url = urlparse(self.esp32_cam_url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ConfigurationError("ESP32_CAM_URL must be a valid HTTP(S) URL.")

        if self.is_production:
            if self.debug:
                raise ConfigurationError(
                    "DEBUG mode must be False in production environment."
                )

            default_dev_url = "postgresql+psycopg://postgres:postgres@localhost:5432/pipevision"
            if (
                self.database_url == default_dev_url
                and not os.getenv("ALLOW_DEV_DATABASE_IN_PRODUCTION")
            ):
                raise ConfigurationError(
                    "Default local DATABASE_URL is not allowed in production without explicit override."
                )

            if "*" in self.cors_origins and not os.getenv("ALLOW_UNSAFE_CORS"):
                raise ConfigurationError(
                    "Wildcard '*' CORS origin is not allowed in production."
                )

            if (
                not self.allow_null_sewer_engine
                and not self.sewer_checkpoint_path.exists()
            ):
                raise ConfigurationError(
                    f"Production Sewer-ML checkpoint not found at '{self.sewer_checkpoint_path}' "
                    "and null engine fallback is disabled."
                )

        # Storage directory validation & creation
        for path_attr, path_val in [
            ("media_import_root", self.media_import_root),
            ("media_storage_root", self.media_storage_root),
        ]:
            try:
                path_val.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                raise ConfigurationError(
                    f"Failed to create or access storage directory '{path_attr}' at '{path_val}': {exc}"
                ) from exc


def _parse_list_env(val: str | None, default: list[str]) -> list[str]:
    if not val or not val.strip():
        return default
    val_str = val.strip()
    if val_str.startswith("[") and val_str.endswith("]"):
        try:
            parsed = json.loads(val_str)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if item]
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return [item.strip() for item in val_str.split(",") if item.strip()]


def _parse_bool_env(val: str | None, default: bool) -> bool:
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def load_settings_from_env() -> Settings:
    """Instantiate Settings from current environment variables."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env not in ("development", "test", "production"):
        env = "development"

    is_prod = env == "production"
    debug_default = not is_prod

    default_cors = ["http://localhost:3000"] if is_prod else ["*"]
    default_hosts = ["localhost", "127.0.0.1"] if is_prod else ["*"]

    settings = Settings(
        environment=env,  # type: ignore[arg-type]
        debug=_parse_bool_env(os.getenv("DEBUG"), debug_default),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/pipevision",
        ),
        db_pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        db_pool_timeout=float(os.getenv("DB_POOL_TIMEOUT", "30.0")),
        db_pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
        sewer_checkpoint_path=Path(
            os.getenv("SEWER_CHECKPOINT_PATH", "experiments/sewer/E009/best.pt")
        ),
        sewer_thresholds_path=Path(
            os.getenv("SEWER_THRESHOLDS_PATH", "experiments/sewer/E009/thresholds.json")
        ),
        allow_null_sewer_engine=_parse_bool_env(
            os.getenv("ALLOW_NULL_SEWER_ENGINE"), False
        ),
        yolo_model_path=os.getenv("YOLO_MODEL_PATH", "yolo11n.pt"),
        yolo_confidence_threshold=float(
            os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.25")
        ),
        media_import_root=Path(os.getenv("MEDIA_IMPORT_ROOT", "data/import")),
        media_storage_root=Path(os.getenv("MEDIA_STORAGE_ROOT", "data/frames")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        cors_origins=_parse_list_env(os.getenv("CORS_ORIGINS"), default_cors),
        allowed_hosts=_parse_list_env(os.getenv("ALLOWED_HOSTS"), default_hosts),
        secret_key=os.getenv("SECRET_KEY"),
        robot_transport_type=os.getenv("ROBOT_TRANSPORT_TYPE", "simulator").lower(),
        robot_host=os.getenv("ROBOT_HOST", "192.168.1.100"),
        robot_port=int(os.getenv("ROBOT_PORT", "5000")),
        robot_serial_port=os.getenv("ROBOT_SERIAL_PORT", "/dev/ttyUSB0"),
        robot_baudrate=int(os.getenv("ROBOT_BAUDRATE", "115200")),
        robot_dry_run=_parse_bool_env(os.getenv("ROBOT_DRY_RUN"), True),
        robot_hardware_enabled=_parse_bool_env(os.getenv("ROBOT_HARDWARE_ENABLED"), False),
        robot_gpio_enabled=_parse_bool_env(os.getenv("ROBOT_GPIO_ENABLED"), False),
        robot_servo_config_json=os.getenv("ROBOT_SERVO_CONFIG_JSON"),
        robot_pico_uart_enabled=_parse_bool_env(os.getenv("ROBOT_PICO_UART_ENABLED"), False),
        robot_pico_uart_port=os.getenv("ROBOT_PICO_UART_PORT", ""),
        robot_pico_uart_baudrate=int(os.getenv("ROBOT_PICO_UART_BAUDRATE", "115200")),
        robot_pico_uart_timeout_s=float(os.getenv("ROBOT_PICO_UART_TIMEOUT_S", "1.0")),
        robot_mpu6050_enabled=_parse_bool_env(os.getenv("ROBOT_MPU6050_ENABLED"), False),
        robot_mpu6050_i2c_bus=int(os.getenv("ROBOT_MPU6050_I2C_BUS", "1")),
        robot_mpu6050_i2c_address=int(os.getenv("ROBOT_MPU6050_I2C_ADDRESS", "104"), 0),
        robot_mpu6050_accelerometer_scale_g=int(os.getenv("ROBOT_MPU6050_ACCELEROMETER_SCALE_G", "2")),
        robot_mpu6050_gyroscope_scale_dps=int(os.getenv("ROBOT_MPU6050_GYROSCOPE_SCALE_DPS", "250")),
        camera_source_type=os.getenv("CAMERA_SOURCE_TYPE", "simulator").lower(),
        esp32_cam_url=os.getenv("ESP32_CAM_URL"),
        esp32_cam_timeout_s=float(os.getenv("ESP32_CAM_TIMEOUT_S", "3.0")),
        max_upload_size_bytes=int(
            os.getenv("MAX_UPLOAD_SIZE_BYTES", str(50 * 1024 * 1024))
        ),
        max_batch_image_count=int(os.getenv("MAX_BATCH_IMAGE_COUNT", "500")),
        max_batch_video_size_bytes=int(
            os.getenv("MAX_BATCH_VIDEO_SIZE_BYTES", str(500 * 1024 * 1024))
        ),
        websocket_heartbeat_interval_s=float(
            os.getenv("WEBSOCKET_HEARTBEAT_INTERVAL_S", "30.0")
        ),
    )

    settings.validate_environment()
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings."""
    return load_settings_from_env()


def reset_settings() -> None:
    """Clear settings cache (for testing)."""
    get_settings.cache_clear()

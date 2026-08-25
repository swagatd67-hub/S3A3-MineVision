"""Unit tests for typed production configuration and environment validation."""

from collections.abc import Generator
from pathlib import Path

import pytest

from backend.app.config import (
    ConfigurationError,
    Settings,
    load_settings_from_env,
    reset_settings,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None, None, None]:
    """Ensure clean environment state for each config test."""
    reset_settings()
    mock_ckpt = tmp_path / "mock_best.pt"
    mock_ckpt.write_bytes(b"mock_weights")

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SEWER_CHECKPOINT_PATH", raising=False)
    monkeypatch.delenv("ALLOW_NULL_SEWER_ENGINE", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)

    # Default valid checkpoint for production tests that don't explicitly test missing checkpoint
    monkeypatch.setenv("SEWER_CHECKPOINT_PATH", str(mock_ckpt))

    yield
    reset_settings()


def test_default_development_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEBUG", "true")
    settings = load_settings_from_env()

    assert settings.is_development is True
    assert settings.is_production is False
    assert settings.debug is True
    assert settings.environment == "development"


def test_production_config_validation_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@prod-db:5432/pipevision")
    monkeypatch.setenv("CORS_ORIGINS", "https://pipevision.app")
    monkeypatch.setenv("ALLOWED_HOSTS", "pipevision.app,api.pipevision.app")

    settings = load_settings_from_env()
    assert settings.is_production is True
    assert settings.debug is False
    assert settings.cors_origins == ["https://pipevision.app"]


def test_production_debug_true_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")

    with pytest.raises(ConfigurationError, match="DEBUG mode must be False"):
        load_settings_from_env()


def test_production_default_db_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "false")

    with pytest.raises(ConfigurationError, match="Default local DATABASE_URL is not allowed"):
        load_settings_from_env()


def test_production_wildcard_cors_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@prod-db:5432/pipevision")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    with pytest.raises(ConfigurationError, match=r"Wildcard '\*' CORS origin is not allowed"):
        load_settings_from_env()


def test_production_missing_checkpoint_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    non_existent = tmp_path / "missing.pt"

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@prod-db:5432/pipevision")
    monkeypatch.setenv("SEWER_CHECKPOINT_PATH", str(non_existent))
    monkeypatch.setenv("ALLOW_NULL_SEWER_ENGINE", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://pipevision.app")

    with pytest.raises(ConfigurationError, match="Production Sewer-ML checkpoint not found"):
        load_settings_from_env()


def test_numeric_limits_validation() -> None:
    settings = Settings(
        max_upload_size_bytes=10 * 1024 * 1024,
        db_pool_size=5,
        db_max_overflow=10,
    )
    assert settings.max_upload_size_bytes == 10485760
    assert settings.db_pool_size == 5

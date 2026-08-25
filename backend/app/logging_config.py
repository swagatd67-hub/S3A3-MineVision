"""Production structured logging configuration for PipeVision."""

import logging
import sys
from contextvars import ContextVar

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    return correlation_id_ctx.get()


def set_correlation_id(cid: str) -> None:
    correlation_id_ctx.set(cid)


class CorrelationFilter(logging.Filter):
    """Inject current correlation_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()  # type: ignore[attr-defined]
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = (
        "%(asctime)s [%(levelname)s] [%(name)s] [correlation_id=%(correlation_id)s] %(message)s"
    )

    formatter = logging.Formatter(log_format)
    filter_ = CorrelationFilter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(filter_)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if setup is called multiple times
    root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, logging.StreamHandler)]
    root_logger.addHandler(handler)

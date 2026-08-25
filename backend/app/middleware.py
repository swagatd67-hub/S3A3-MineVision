"""Production HTTP middleware for correlation tracing, security, and payload validation."""

import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.logging_config import set_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Injects or propagates X-Correlation-ID header across API requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        header_name = "X-Correlation-ID"
        correlation_id = request.headers.get(header_name) or request.headers.get("X-Request-ID")

        if not correlation_id or not correlation_id.strip():
            correlation_id = f"req-{uuid.uuid4().hex[:12]}"
        else:
            correlation_id = correlation_id.strip()

        set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)
        response.headers[header_name] = correlation_id
        return response

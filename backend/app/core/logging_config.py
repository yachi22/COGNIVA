import contextvars
import logging
import re
import sys
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.sanitizer import sanitize_log_message

# Context variable preserving correlation / request ID across async tasks
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Returns current async task correlation ID or fallback to empty string."""
    return correlation_id_ctx.get() or ""


def set_correlation_id(correlation_id: str) -> contextvars.Token:
    """Explicitly sets correlation ID for current context (e.g. background tasks)."""
    return correlation_id_ctx.set(correlation_id)


class CorrelationFilter(logging.Filter):
    """
    Logging filter that:
    1. Injects correlation_id into all LogRecords.
    2. Redacts sensitive credentials (passwords, tokens, API keys) from record.msg and args.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Attach correlation ID
        record.correlation_id = get_correlation_id() or "system"

        # Sanitize message
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)

        # Sanitize arguments if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: sanitize_log_message(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(sanitize_log_message(str(a)) if isinstance(a, str) else a for a in record.args)

        return True


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configures structured logging across root, uvicorn, and cogniva loggers.
    Format: [timestamp] [level] [req_id:correlation_id] [logger_name] message
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [req_id:%(correlation_id)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Ensure stream handler exists
    handler: Optional[logging.Handler] = None
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler):
            handler = h
            break

    if not handler:
        handler = logging.StreamHandler(sys.stdout)
        root_logger.addHandler(handler)

    handler.setFormatter(formatter)

    # Add correlation and redaction filter if not already attached
    if not any(isinstance(f, CorrelationFilter) for f in handler.filters):
        handler.addFilter(CorrelationFilter())

    # Configure cogniva namespace loggers
    for logger_name in ["cogniva", "uvicorn", "uvicorn.access", "uvicorn.error"]:
        lg = logging.getLogger(logger_name)
        lg.setLevel(level)
        if not any(isinstance(f, CorrelationFilter) for f in lg.filters):
            lg.addFilter(CorrelationFilter())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware that extracts or generates a correlation ID for each request.
    Propagates correlation ID through response headers ('X-Correlation-ID', 'X-Request-ID')
    and sets the async contextvar for structured logging.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Read existing header or generate a fresh UUID
        incoming_id = request.headers.get("x-correlation-id") or request.headers.get("x-request-id")
        if incoming_id and re.match(r"^[a-zA-Z0-9_\-]{1,64}$", incoming_id.strip()):
            correlation_id = incoming_id.strip()
        else:
            correlation_id = str(uuid.uuid4())

        # 2. Store in contextvar and request state
        token = correlation_id_ctx.set(correlation_id)
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)

        # 3. Echo correlation ID on outbound response
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = correlation_id
        return response


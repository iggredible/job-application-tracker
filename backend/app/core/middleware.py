import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from app.core.logging import REQUEST_LOGGER

logger = logging.getLogger(REQUEST_LOGGER)
error_logger = logging.getLogger("app.error")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """One JSON log line per request, and the request ID returned in X-Request-ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Answer here so the 500 carries the request ID too. The traceback is kept on its
            # own logger, so the request logger still emits exactly one line per request.
            error_logger.exception("Unhandled error in request %s", request_id)
            response = PlainTextResponse("Internal Server Error", status_code=500)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                }
            )
        )
        response.headers["X-Request-ID"] = request_id
        return response

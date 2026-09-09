import contextvars
import logging
import sys
import time
import uuid

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    """Return the active request id, or '' when no request is in flight."""
    return request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    """Attach the active request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


def setup_logging(level: str = "INFO") -> None:
    """Configure a consistent log format on the root logger."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s | %(levelname)-8s | "
            "req=%(request_id)s | %(name)s | %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stdout,
        force=True,
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())


class RequestLoggingMiddleware:
    """Pure-ASGI middleware that logs one access line per HTTP request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status_code = None
        access_log = logging.getLogger("access")

        async def send_with_context(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status")
                headers = list(message.get("headers", ()))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            method = scope.get("method", "")
            path = scope.get("path", "")
            access_log.info(
                "%s %s -> %s (%d ms)",
                method,
                path,
                status_code if status_code is not None else "ERR",
                round(duration_ms),
            )
            request_id_ctx.reset(token)

    @staticmethod
    def _request_id(scope) -> str:
        for name, value in scope.get("headers", ()):
            if name.lower() == b"x-request-id":
                incoming = value.decode("latin-1").strip()
                if incoming:
                    return incoming
        return uuid.uuid4().hex
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

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        kind = scope.get("type")
        if kind not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status_code = None
        method = scope.get("method", "GET") if kind == "http" else "WS"
        path = scope.get("path", "")
        access_log = logging.getLogger("access")

        async def send_with_context(message):
            nonlocal status_code
            message_type = message.get("type")

            if message_type in ("http.response.start", "websocket.http.response.start"):
                status_code = message.get("status")
                headers = list(message.get("headers", ()))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            elif message_type == "websocket.accept":
                status_code = 101
            elif message_type == "websocket.close" and status_code is None:
                # Server closed before accepting -> represent the rejection.
                status_code = 499

            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
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
"""Request context: correlation id + one structured access-log line per request.

Railway's log drain is the primary observability surface, so every request gets
exactly one line keyed by a correlation id that is also returned in the
``X-Request-ID`` response header (clients can quote it in support tickets, and
the global 500 handler echoes it so a user-reported failure is greppable).
"""
import logging
import time
import uuid

log = logging.getLogger("access")

# Uptime probes hit these constantly - keep them out of the access log.
SKIP_PATHS = {"/metrics", "/api/health", "/readyz"}


def _request_id(scope: dict) -> str:
    for name, value in scope.get("headers", []):
        if name == b"x-request-id" and value:
            return value.decode("latin-1", "replace")[:64]
    return uuid.uuid4().hex[:16]


class RequestContextMiddleware:
    """ASGI middleware: attach ``state.request_id`` and log method/path/status/ms."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = _request_id(scope)
        scope.setdefault("state", {})["request_id"] = rid
        path = scope.get("path", "?")
        method = scope.get("method", "?")
        status_holder = {"status": 500}
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                message.setdefault("headers", []).append(
                    (b"x-request-id", rid.encode("latin-1"))
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if path not in SKIP_PATHS:
                elapsed_ms = (time.perf_counter() - start) * 1000
                log.info(
                    "%s %s %s %.1fms rid=%s",
                    method, path, status_holder["status"], elapsed_ms, rid,
                )

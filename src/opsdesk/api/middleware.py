import json
import logging
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from opsdesk.api.errors import error_response

LOGGER_NAME = "opsdesk.requests"
logger = logging.getLogger(LOGGER_NAME)

KNOWN_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
    "TRACE",
    "CONNECT",
}


def configure_request_logging() -> None:
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


class RequestDiagnosticsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        started_at = perf_counter()
        response_started = False
        status_code = None
        unexpected_error = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_started, status_code

            if message["type"] == "http.response.start":
                message = dict(message)
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers

                status_code = message["status"]
                response_started = True

            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            unexpected_error = True

            if response_started:
                raise RuntimeError("Response failed after start.") from None

            response = error_response("internal_error")
            await response(scope, receive, send_with_request_id)
        finally:
            route = scope.get("route")
            route_template = getattr(route, "path", None)
            if not isinstance(route_template, str):
                route_template = "<unmatched>"

            method = scope.get("method", "")
            if method not in KNOWN_METHODS:
                method = "OTHER"

            event = {
                "event": "request_finished",
                "request_id": request_id,
                "method": method,
                "route": route_template[:200],
                "status_code": status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "response_started": response_started,
                "unexpected_error": unexpected_error,
            }

            level = logging.ERROR if unexpected_error else logging.INFO
            logger.log(level, json.dumps(event))

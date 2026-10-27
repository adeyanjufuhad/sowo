"""Logging: one line per request with a request id, JSON by default, and no phone numbers or secrets in the output."""

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("app.request")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# Not worth a log line when they succeed: load balancers call them every few seconds.
_QUIET_PATHS = {"/health", "/ready"}

# Long digit runs are phone numbers (or WhatsApp number ids); keep only the last three so a line is still traceable.
_DIGITS = re.compile(r"(?<!\w)\+?(\d{7,})(?!\w)")
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_PAYSTACK_KEY = re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]+")


def redact(text: str) -> str:
    text = _BEARER.sub(r"\1[redacted]", text)
    text = _PAYSTACK_KEY.sub("[redacted]", text)
    return _DIGITS.sub(lambda match: "***" + match.group(1)[-3:], text)


class Formatter(logging.Formatter):
    """JSON (one object per line, for a log host) or plain text (for a terminal). Both run the redaction."""

    def __init__(self, *, as_json: bool) -> None:
        super().__init__()
        self.as_json = as_json

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        fields: dict[str, object] = getattr(record, "fields", {})
        request_id = request_id_var.get()
        stamp = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
        error = self.formatException(record.exc_info) if record.exc_info else None
        if self.as_json:
            entry: dict[str, object] = {"ts": stamp, "level": record.levelname, "logger": record.name, "msg": message}
            if request_id:
                entry["request_id"] = request_id
            entry.update(fields)
            if error:
                entry["exc"] = error
            return redact(json.dumps(entry, default=str, ensure_ascii=False))
        parts = [stamp, record.levelname, record.name, message]
        if request_id:
            parts.append(f"request_id={request_id}")
        parts.extend(f"{key}={value}" for key, value in fields.items())
        line = " ".join(str(part) for part in parts)
        return redact(f"{line}\n{error}" if error else line)


def configure_logging(settings: Settings) -> None:
    """Send every log line, ours and the libraries', through one formatter on stderr."""
    formatter = Formatter(as_json=settings.log_format == "json")
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_sowo", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler._sowo = True  # type: ignore[attr-defined]
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    # Uvicorn installs its own handlers. Its access log would also print query strings, which carry the WhatsApp
    # verify token, and the request middleware below already logs every request.
    for name in ("uvicorn", "uvicorn.error"):
        for existing in logging.getLogger(name).handlers:
            existing.setFormatter(formatter)
    logging.getLogger("uvicorn.access").disabled = True
    # httpx logs the full URL of every outgoing call at INFO, which for WhatsApp and Paystack names numbers and ids.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


class RequestLogMiddleware:
    """Gives each request an id (the caller's X-Request-ID if it is sane), echoes it back and logs one line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).get("x-request-id", "")
        request_id = supplied if _VALID_REQUEST_ID.match(supplied) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        logged = False

        def log() -> None:
            nonlocal logged
            if logged:
                return
            logged = True
            # The route's pattern, never the URL: ids, phone numbers and the query string stay out of the logs.
            route = scope.get("route")
            path = getattr(route, "path", None) or "unmatched"
            if path in _QUIET_PATHS and status < 400:
                return
            level = logging.ERROR if status >= 500 else logging.WARNING if status == 429 else logging.INFO
            logger.log(
                level,
                "request",
                extra={
                    "fields": {
                        "method": scope["method"],
                        "path": path,
                        "status": status,
                        "ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append("x-request-id", request_id)
            await send(message)
            # Log when the response has gone out, not after any background work (like a model call) that follows it.
            if message["type"] == "http.response.body" and not message.get("more_body"):
                log()

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            status = 500
            log()
            raise
        finally:
            request_id_var.reset(token)

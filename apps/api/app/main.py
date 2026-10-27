import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.db import get_db, init_db
from app.observability import RequestLogMiddleware, configure_logging
from app.ratelimit import RateLimitMiddleware
from app.routes import router
from app.routes_auth import router as auth_router
from app.routes_catalog import router as catalog_router
from app.routes_payments import router as payments_router
from app.routes_simulator import router as simulator_router
from app.routes_vendor import router as vendor_router
from app.routes_webhooks import router as webhooks_router

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # No background polling: on a serverless database a query every few seconds keeps the compute awake all
    # month. Overdue holds are released when stock is read, when an order is placed and when orders are listed.
    if settings.environment == "production" and settings.simulator_enabled:
        logger.warning("SIMULATOR_ENABLED is on in production: /simulator/* has no sign-in and anyone can call it")
    init_db()
    yield


app = FastAPI(title="Sowo API", lifespan=lifespan)
# The last one added is the outermost: CORS wraps the request log, which wraps the rate limit, so refused requests
# are logged and carry CORS headers.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
app.include_router(router)
app.include_router(auth_router)
app.include_router(vendor_router)
app.include_router(catalog_router)
app.include_router(payments_router)
app.include_router(webhooks_router)
app.include_router(simulator_router)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: object, exc: StarletteHTTPException) -> JSONResponse:
    codes = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 404: "NOT_FOUND", 409: "CONFLICT", 429: "RATE_LIMITED"}
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": codes.get(exc.status_code, "INTERNAL"), "message": message}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: object, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "BAD_REQUEST", "message": "Invalid request body"}},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: object, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL", "message": "Something went wrong on our side"}},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Is the process up? Deliberately never touches the database, so a health probe can't keep Neon awake."""
    return {"status": "ok"}


@app.get("/ready")
def ready(session: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    """Can it serve? Checks the database connection. Point a deploy's readiness check here, not the liveness one."""
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - whatever the driver raises means "not ready"
        # The class only: a driver's message can include the connection string.
        logger.error("Readiness check failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(content={"status": "ready"})

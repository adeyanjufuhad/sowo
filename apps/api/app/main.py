from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.db import init_db
from app.routes import router
from app.routes_auth import router as auth_router
from app.routes_payments import router as payments_router
from app.routes_simulator import router as simulator_router
from app.routes_vendor import router as vendor_router
from app.routes_webhooks import router as webhooks_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # No background polling: on a serverless database a query every few seconds keeps the compute awake all
    # month. Overdue holds are released when stock is read, when an order is placed and when orders are listed.
    init_db()
    yield


app = FastAPI(title="Sowo API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(auth_router)
app.include_router(vendor_router)
app.include_router(payments_router)
app.include_router(webhooks_router)
app.include_router(simulator_router)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: object, exc: StarletteHTTPException) -> JSONResponse:
    codes = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 404: "NOT_FOUND", 409: "CONFLICT"}
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.services.orders import expire_holds

settings = get_settings()


async def hold_expiry_worker() -> None:
    while True:
        await asyncio.sleep(30)
        with SessionLocal() as session:
            with session.begin():
                expire_holds(session)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    worker = asyncio.create_task(hold_expiry_worker())
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title="Sowo API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

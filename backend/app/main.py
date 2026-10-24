from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from starlette.exceptions import HTTPException

from .config import settings
from .db import Base, SessionLocal, engine
from .models import User
from .routers import admin, auth, availability, events, feed, files, organizer, users
from .services import embeddings

CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
         409: "conflict", 422: "invalid", 429: "rate_limited", 503: "unavailable"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    if settings.app_env != "test":
        embeddings.start_background_load()
    if settings.demo_mode:
        with SessionLocal() as db:
            empty = db.scalar(select(func.count()).select_from(User)) == 0
            if empty:
                from .seed.seed import seed

                seed(db)
    yield


app = FastAPI(title="ShowUp API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error(_req: Request, exc: HTTPException):
    return JSONResponse(
        {"error": {"code": CODES.get(exc.status_code, "error"), "message": exc.detail}},
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_req: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:])
    message = f"{field}: {first.get('msg', 'Invalid input')}" if field else first.get("msg", "Invalid input")
    return JSONResponse({"error": {"code": "invalid", "message": message}}, status_code=422)


for r in (auth.router, users.router, availability.router, feed.router, events.router, organizer.router, admin.router, files.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True, "demo_mode": settings.demo_mode, "ai_live": settings.use_live_ai, "matching": embeddings.backend()}

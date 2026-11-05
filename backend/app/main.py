import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .config import settings
from .db import Base, SessionLocal, engine
from .routers import admin, alerts, auth, org_profile, public, availability, events, feed, files, notifications, organizer, registrations, together, users
from .security import COOKIE_NAME, CSRF_COOKIE, CSRF_HEADER, same
from .services import embeddings, jobs, stream

log = logging.getLogger("showup")

CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
         409: "conflict", 422: "invalid", 429: "rate_limited", 503: "unavailable"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.app_env == "test":
        Base.metadata.create_all(engine)
        from .services.categories import ensure_rows

        with SessionLocal() as db:
            ensure_rows(db)
    else:
        from .migrate import upgrade

        upgrade()  # production starts from an empty, fully migrated database
    stream.bind_loop(asyncio.get_running_loop())
    if settings.app_env != "test":
        embeddings.start_background_load()
        jobs.start_scheduler()
    yield
    jobs.stop_scheduler()


app = FastAPI(title="ShowUp API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def csrf_and_headers(request: Request, call_next):
    """Double-submit CSRF check for cookie sessions, plus a few safe default headers."""
    if (request.method in UNSAFE and request.url.path.startswith("/api/") and request.cookies.get(COOKIE_NAME)
            and not request.headers.get("authorization")):
        if not same(request.headers.get(CSRF_HEADER), request.cookies.get(CSRF_COOKIE)):
            return JSONResponse({"error": {"code": "csrf", "message": "Your session needs a refresh. Reload the page and try again."}},
                                status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


@app.exception_handler(HTTPException)
async def http_error(_req: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        code, message = exc.detail.get("code", "error"), exc.detail.get("message", "Something went wrong.")
    else:
        code, message = CODES.get(exc.status_code, "error"), exc.detail
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"error": {"code": "server_error", "message": "Something went wrong on our side. Try again in a moment."}},
                        status_code=500)


@app.exception_handler(RequestValidationError)
async def validation_error(_req: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:])
    message = f"{field}: {first.get('msg', 'Invalid input')}" if field else first.get("msg", "Invalid input")
    return JSONResponse({"error": {"code": "invalid", "message": message}}, status_code=422)


for r in (auth.router, users.router, availability.router, feed.router, events.router, organizer.router, admin.router,
          files.router, registrations.router, notifications.router, together.router, alerts.router, public.router, org_profile.router):
    app.include_router(r, prefix="/api")


@app.get("/health", include_in_schema=False)
@app.get("/api/health")
def health():
    """Cheap liveness check for Render and for the app's wake-up retry. Touches no database."""
    return {"ok": True}


# One-service deploys (Render): serve the built SPA from the same origin as the API.
if settings.static_dir and (Path(settings.static_dir) / "index.html").is_file():
    STATIC = Path(settings.static_dir).resolve()
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "Not Found")
        file = (STATIC / path).resolve()
        if path and file.is_file() and STATIC in file.parents:
            return FileResponse(file)
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

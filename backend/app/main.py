"""App setup: routes, error handling, security headers and CORS.

Run locally (from backend/, venv active):
    uvicorn app.main:create_app --factory --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .db import create_pool
from .errors import GENERIC_SERVER_ERROR, error_body, register_error_handlers
from .routers import auth, staff, tickets
from .schemas import Health

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("support")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pool = create_pool(settings.database_url)
        yield
        app.state.pool.close()

    # Interactive docs only in development. The contract is docs/openapi.yaml.
    docs_on = not settings.is_production
    app = FastAPI(
        title="Support Ticket System API",
        lifespan=lifespan,
        docs_url="/docs" if docs_on else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_on else None,
    )
    app.state.settings = settings

    register_error_handlers(app)

    @app.get("/health", response_model=Health, tags=["health"])
    def health():
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(staff.router)
    app.include_router(tickets.router)

    add_middleware(app, settings)
    return app


def add_middleware(app: FastAPI, settings: Settings) -> None:
    # Order matters: the LAST one added runs FIRST. So CORS wraps everything,
    # and even error responses get CORS and security headers.

    @app.middleware("http")
    async def catch_unexpected_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            # Full details (stack trace, SQL error) go to the server log only.
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content=error_body("internal_error", GENERIC_SERVER_ERROR))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"  # responses may contain private data
        if not request.url.path.startswith("/docs"):  # the dev docs page needs scripts
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,  # we use the Authorization header, not cookies
    )

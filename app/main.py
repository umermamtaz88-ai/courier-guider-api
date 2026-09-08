import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.logging import get_logger, setup_logging

settings = get_settings()


def _run_migrations() -> None:
    """Apply Alembic migrations on boot in production (Neon/managed DB)."""
    if settings.app_env not in {"production", "prod", "staging"}:
        return
    from alembic import command
    from alembic.config import Config

    logger = get_logger("courier_guider.migrations")
    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        logger.info("alembic_upgrade_complete")
    except Exception as exc:
        # Do not crash the app if schema is already applied or migrate fails transiently.
        logger.error("alembic_upgrade_failed", error=str(exc))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _run_migrations()
    yield


def create_app() -> FastAPI:
    setup_logging()

    logger = get_logger("courier_guider.startup")
    logger.info(
        "llm_config",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        llm_base_url=settings.llm_base_url,
        llm_api_key_configured=bool(settings.llm_api_key),
        llm_max_retries=settings.llm_max_retries,
    )
    logger.info(
        "web_search_config",
        web_search_provider=settings.web_search_provider,
        tavily_configured=bool(settings.tavily_api_key),
        tavily_search_depth=settings.tavily_search_depth,
        tavily_max_results=settings.tavily_max_results,
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        from app.errors import code_from_detail
        from app.logging import get_logger

        request_id = getattr(request.state, "request_id", None)
        logger = get_logger("api")

        if isinstance(exc.detail, dict) and "code" in exc.detail:
            code = exc.detail["code"]
            message = exc.detail.get("message", str(exc.detail))
        else:
            detail_text = str(exc.detail)
            code = code_from_detail(exc.status_code, detail_text)
            message = detail_text

        auth_header_present = bool(request.headers.get("authorization"))
        if request.url.path.endswith("/chat") and request.method == "POST":
            logger.info(
                "chat_auth",
                request_id=request_id,
                route="/chat",
                method="POST",
                status_code=exc.status_code,
                error_code=code,
                user_authenticated=exc.status_code not in (401, 403),
                authorization_header_present=auth_header_present,
                token_present=auth_header_present,
                auth_failure_reason=code if exc.status_code in (401, 403) else None,
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id,
                }
            },
            headers=getattr(exc, "headers", None) or {},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        from app.logging import get_logger

        request_id = getattr(request.state, "request_id", None)
        log = get_logger("api")
        log.exception("unhandled_exception", request_id=request_id, path=str(request.url.path))
        if settings.debug:
            detail = str(exc)
        else:
            detail = "Internal server error"
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": detail,
                    "request_id": request_id,
                }
            },
        )

    app.include_router(api_router)
    app.include_router(health_router)

    @app.get("/")
    def root():
        return {"message": settings.app_name, "version": settings.app_version, "docs": "/docs"}

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=settings.debug)

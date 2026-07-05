import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.comments import router as comments_router
from api.routes.documents import router as documents_router
from api.routes.drafts import router as drafts_router
from api.routes.exports import router as exports_router
from api.routes.patches import router as patches_router
from api.routes.sources import router as sources_router
from api.routes.templates import router as templates_router
from api.routes.validation import router as validation_router
from config.logging import setup_logging
from config.settings import get_settings

logger = logging.getLogger("docforge")
settings = get_settings()


def create_app() -> FastAPI:
    setup_logging()
    # In production: refuse insecure defaults at boot rather than logging and serving.
    if settings.jwt_secret == "change-me-in-production":
        if settings.is_production:
            raise RuntimeError(
                "JWT_SECRET is still the default 'change-me-in-production'. "
                "Set a strong, unique JWT_SECRET before starting in production."
            )
        logger.critical("JWT secret is the insecure default — set JWT_SECRET (dev only).")

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if "*" in origins:
        if settings.is_production:
            raise RuntimeError(
                "CORS wildcard '*' with credentials is forbidden in production. "
                "Set explicit origins in CORS_ORIGINS."
            )
        logger.critical("CORS wildcard '*' with credentials is insecure (dev only).")

    # Hide API docs in production.
    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"

    app = FastAPI(
        title="DocForge API",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def validate_security_settings():
        import asyncio

        if not settings.minio_access_key or not settings.minio_secret_key:
            logger.warning(
                "MinIO credentials not configured. Set MINIO_ACCESS_KEY and MINIO_SECRET_KEY."
            )

        def _ensure_bucket() -> str:
            from minio import Minio
            client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_use_ssl,
            )
            if not client.bucket_exists(settings.minio_bucket):
                client.make_bucket(settings.minio_bucket)
                return "created"
            return "exists"

        # Blocking MinIO I/O off the event loop so a slow/unreachable MinIO
        # doesn't stall startup/health for every request.
        try:
            result = await asyncio.to_thread(_ensure_bucket)
            logger.info("MinIO bucket '%s' %s", settings.minio_bucket, result)
        except Exception as e:
            logger.warning("Could not verify/create MinIO bucket: %s", e)

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(drafts_router, prefix="/api/v1")
    app.include_router(patches_router, prefix="/api/v1")
    app.include_router(comments_router, prefix="/api/v1")
    app.include_router(validation_router, prefix="/api/v1")
    app.include_router(templates_router, prefix="/api/v1")
    app.include_router(sources_router, prefix="/api/v1")
    app.include_router(exports_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()

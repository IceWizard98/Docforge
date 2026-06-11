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
from api.routes.templates import router as templates_router
from api.routes.validation import router as validation_router
from config.settings import get_settings

logger = logging.getLogger("docforge")
settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DocForge API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    origins = settings.cors_origins.split(",")

    for origin in origins:
        if origin.strip() == "*":
            logger.critical(
                "CORS: allow_credentials=True with wildcard origin '*' is insecure. "
                "Set specific origins in cors_origins."
            )
            break

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def validate_security_settings():
        if settings.jwt_secret == "change-me-in-production":
            logger.critical(
                "JWT secret is still the default 'change-me-in-production'. "
                "Set a strong, unique JWT_SECRET in production."
            )
        if not settings.minio_access_key or not settings.minio_secret_key:
            logger.warning(
                "MinIO credentials not configured. Set MINIO_ACCESS_KEY and MINIO_SECRET_KEY."
            )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(drafts_router, prefix="/api/v1")
    app.include_router(patches_router, prefix="/api/v1")
    app.include_router(comments_router, prefix="/api/v1")
    app.include_router(validation_router, prefix="/api/v1")
    app.include_router(templates_router, prefix="/api/v1")
    app.include_router(exports_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()

"""Point d'entrée de l'API mobile Dorea (FastAPI).

Assemble l'application : configuration, logging, CORS, gestion d'erreurs de
domaine et routeur `/api/mobile`.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app._shared.interface.exception_handlers import register_exception_handlers
from app.api.router import api_router, backoffice_router, public_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger("startup")
    logger.info("api_starting", environment=settings.environment, prefix=settings.api_prefix)
    yield
    await engine.dispose()
    logger.info("api_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Dorea Church — Backend",
        version="0.1.0",
        summary=(
            "Backend monolithe. Possède le schéma et le fait évoluer. Deux surfaces : "
            "/api/backoffice (PWA Next.js) et /api/mobile (Flutter)."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Jamais joker + credentials (sinon n'importe quelle origine lit les réponses créditées) :
    # avec `*`, on désactive `allow_credentials`. En prod, le joker est de toute façon refusé
    # au démarrage (voir Settings._enforce_prod_hardening).
    wildcard_cors = "*" in settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=not wildcard_cors,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _hsts = settings.environment != "local"

    @app.middleware("http")
    async def _security_headers(request, call_next):
        """En-têtes de durcissement sur toutes les réponses (clickjacking, MIME-sniffing, TLS)."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if _hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    register_exception_handlers(app)

    # Sert les images stockées **localement** (dev) sous `media_base_url` ; en prod (S3), les
    # URLs pointent ailleurs et ce montage reste simplement inutilisé.
    if settings.s3_endpoint_url is None:
        media_dir = Path(settings.media_dir)
        media_dir.mkdir(parents=True, exist_ok=True)
        app.mount(
            settings.media_base_url, StaticFiles(directory=media_dir), name="media"
        )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(backoffice_router, prefix=settings.backoffice_prefix)
    app.include_router(public_router, prefix="/api")

    return app


app = create_app()

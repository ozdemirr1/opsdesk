from fastapi import FastAPI

from opsdesk.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="OpsDesk",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    return app

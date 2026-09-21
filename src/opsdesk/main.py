from fastapi import FastAPI

from opsdesk.api.errors import ApiError, handle_api_error
from opsdesk.api.middleware import (
    RequestDiagnosticsMiddleware,
    configure_request_logging,
)
from opsdesk.api.transport import install_transport_handlers
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
    install_transport_handlers(app)

    app.add_exception_handler(ApiError, handle_api_error)

    configure_request_logging()
    app.add_middleware(RequestDiagnosticsMiddleware)

    return app

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.api.errors import ApiError, handle_api_error
from opsdesk.api.middleware import (
    RequestDiagnosticsMiddleware,
    configure_request_logging,
)
from opsdesk.api.transport import install_transport_handlers
from opsdesk.config import Settings
from opsdesk.db.config import DatabaseSettings
from opsdesk.db.connection import create_database_engine
from opsdesk.db.session import create_session_factory
from opsdesk.identity.passwords import PasswordHasher
from opsdesk.identity.router import router as identity_router
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import Clock, utc_now
from opsdesk.organizations.router import router as organizations_router
from opsdesk.tickets.router import router as tickets_router


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    token_settings: TokenSettings | None = None,
    token_clock: Clock = utc_now,
) -> FastAPI:
    if settings is None:
        settings = Settings()

    if token_settings is None and settings.environment != "test":
        token_settings = TokenSettings()

    login_password_hasher: PasswordHasher | None = None
    dummy_password_hash: str | None = None

    if token_settings is not None:
        login_password_hasher = PasswordHasher()
        dummy_password_hash = login_password_hasher.create_dummy_hash()

    owned_engine: Engine | None = None

    if session_factory is None and settings.environment != "test":
        owned_engine = create_database_engine(DatabaseSettings())
        session_factory = create_session_factory(owned_engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owned_engine is not None:
                owned_engine.dispose()

    app = FastAPI(
        title="OpsDesk",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    app.state.session_factory = session_factory
    app.state.token_settings = token_settings
    app.state.token_clock = token_clock
    app.state.login_password_hasher = login_password_hasher
    app.state.dummy_password_hash = dummy_password_hash

    install_transport_handlers(app)
    app.include_router(identity_router)
    app.include_router(organizations_router)
    app.include_router(tickets_router)

    app.add_exception_handler(ApiError, handle_api_error)

    configure_request_logging()
    app.add_middleware(RequestDiagnosticsMiddleware)

    return app

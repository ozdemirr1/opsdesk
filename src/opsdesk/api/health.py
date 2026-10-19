from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.api.errors import ApiError
from opsdesk.db.session import session_scope

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(request: Request) -> dict[str, str]:
    factory: sessionmaker[Session] | None = getattr(
        request.app.state,
        "session_factory",
        None,
    )

    if factory is None:
        raise ApiError("service_unavailable")

    try:
        with session_scope(factory) as session:
            result = session.scalar(text("SELECT 1"))
    except SQLAlchemyError:
        raise ApiError("service_unavailable") from None

    if result != 1:
        raise ApiError("service_unavailable")

    return {"status": "ready"}

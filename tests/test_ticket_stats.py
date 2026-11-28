import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.identity.token_config import TokenSettings
from opsdesk.main import create_app
from opsdesk.tickets.dependencies import get_ticket_read_service
from opsdesk.tickets.read_models import TicketReadAccess, TicketStatsRead
from opsdesk.tickets.repositories import TicketConcurrencyError
from opsdesk.tickets.services import TicketReadService


class StatsRepository:
    def __init__(self, counts=None, access=None, error=None):
        self.counts = counts or {}
        self.access = access or TicketReadAccess(True, True, True)
        self.error = error
        self.calls = []

    def stats_for_actor(self, **scope):
        self.calls.append(scope)
        if self.error:
            raise self.error
        return TicketStatsRead(self.access, self.counts)


@pytest.mark.parametrize("counts", [{}, {"open": 2, "closed": 1}])
def test_counts_zero_fill_total_and_authenticated_scope(counts):
    repo = StatsRepository(counts)
    with client_for(TicketReadService(repo)) as client:
        response = client.get("/organizations/2/ticket-stats")
    assert response.status_code == 200
    expected = dict(open=0, in_progress=0, resolved=0, closed=0) | counts
    assert response.json() == {"total": sum(counts.values()), "by_status": expected}
    assert repo.calls == [{"actor_user_id": 42, "organization_id": 2}]


@pytest.mark.parametrize("counts", [{}, {"open": 99}])
@pytest.mark.parametrize(
    "access,status,code",
    [
        (TicketReadAccess(False, True, True), 401, "unauthenticated"),
        (TicketReadAccess(True, False, True), 403, "organization_access_denied"),
        (TicketReadAccess(True, True, False), 403, "organization_suspended"),
        (TicketReadAccess(True, False, False), 403, "organization_access_denied"),
    ],
)
def test_access_failure_never_returns_counts(counts, access, status, code):
    with client_for(TicketReadService(StatsRepository(counts, access))) as client:
        response = client.get("/organizations/2/ticket-stats")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "by_status" not in response.json()


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-token"])
def test_authentication_precedes_stats_repository(authorization):
    repo = StatsRepository()
    with client_for(TicketReadService(repo), authenticated=False) as client:
        response = client.get(
            "/organizations/2/ticket-stats",
            headers=({} if authorization is None else {"Authorization": authorization}),
        )
    assert response.status_code == 401
    assert repo.calls == []


@pytest.mark.parametrize(
    "target",
    [
        "/organizations/0/ticket-stats",
        "/organizations/9223372036854775808/ticket-stats",
        "/organizations/2/ticket-stats?requester_membership_id=8",
        "/organizations/2/ticket-stats?status=open",
    ],
)
def test_invalid_scope_or_unexpected_query_is_rejected(target):
    repo = StatsRepository()
    with client_for(TicketReadService(repo)) as client:
        response = client.get(target)
    assert response.status_code == 422
    assert repo.calls == []


@pytest.mark.parametrize(
    "error,status,code",
    [
        (TicketConcurrencyError(), 503, "concurrency_busy"),
        (RuntimeError("private-query-details"), 500, "internal_error"),
    ],
)
def test_errors_keep_safe_contract(error, status, code):
    with client_for(TicketReadService(StatsRepository(error=error))) as client:
        response = client.get("/organizations/2/ticket-stats")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "private-query-details" not in response.text


def client_for(service, authenticated=True):
    app = create_app(
        Settings(environment="test"),
        token_settings=TokenSettings(secret="synthetic-stats-test-key-" * 3),
    )
    app.dependency_overrides[get_ticket_read_service] = lambda: service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: User(
            42, "stats@example.com", "synthetic-hash", True
        )
    return TestClient(app, raise_server_exceptions=False)

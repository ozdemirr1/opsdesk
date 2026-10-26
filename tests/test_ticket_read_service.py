from datetime import UTC, datetime

import pytest

from opsdesk.tickets.models import Ticket
from opsdesk.tickets.read_models import (
    TicketDetailRead,
    TicketFilters,
    TicketList,
    TicketListRead,
    TicketReadAccess,
)
from opsdesk.tickets.repositories import TicketConcurrencyError
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
    TicketReadBusyError,
    TicketReadService,
)


class ReadRepository:
    def __init__(
        self, access=TicketReadAccess(True, True, True), ticket=None, error=None
    ):
        self.access, self.ticket, self.error = access, ticket, error
        self.calls = []

    def list_for_actor(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return TicketListRead(
            self.access, TicketList((), 12, kwargs["limit"], kwargs["offset"])
        )

    def get_for_actor(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return TicketDetailRead(self.access, self.ticket)


def call(service, operation):
    if operation == "list":
        return service.list_for_actor(
            actor_user_id=1,
            organization_id=2,
            filters=TicketFilters(q="email"),
            limit=20,
            offset=20,
        )
    return service.get_for_actor(actor_user_id=1, organization_id=2, ticket_id=3)


@pytest.mark.parametrize("operation", ["list", "detail"])
@pytest.mark.parametrize(
    "access,error",
    [
        (TicketReadAccess(False, False, False), TicketActorUnavailableError),
        (TicketReadAccess(True, False, False), TicketOrganizationAccessDeniedError),
        (TicketReadAccess(True, True, False), TicketOrganizationSuspendedError),
    ],
)
def test_access_precedes_empty_or_missing_result(operation, access, error):
    with pytest.raises(error):
        call(TicketReadService(ReadRepository(access)), operation)


def test_beyond_end_page_keeps_total_and_forwards_scope():
    repo = ReadRepository()
    result = call(TicketReadService(repo), "list")
    assert result == TicketList((), 12, 20, 20)
    assert repo.calls == [
        {
            "actor_user_id": 1,
            "organization_id": 2,
            "filters": TicketFilters(q="email"),
            "limit": 20,
            "offset": 20,
        }
    ]


def test_visible_detail_and_missing_detail():
    now = datetime(2026, 10, 26, tzinfo=UTC)
    ticket = Ticket(3, 2, 4, 4, None, "Title", "Description", "closed", "low", now, now)
    repo = ReadRepository(ticket=ticket)
    assert call(TicketReadService(repo), "detail") == ticket
    assert repo.calls == [{"actor_user_id": 1, "organization_id": 2, "ticket_id": 3}]
    with pytest.raises(TicketNotFoundError):
        call(TicketReadService(ReadRepository()), "detail")


@pytest.mark.parametrize("operation", ["list", "detail"])
def test_contention_is_mapped_but_unexpected_errors_propagate(operation):
    with pytest.raises(TicketReadBusyError):
        call(
            TicketReadService(ReadRepository(error=TicketConcurrencyError())), operation
        )
    with pytest.raises(RuntimeError):
        call(
            TicketReadService(ReadRepository(error=RuntimeError("private"))), operation
        )

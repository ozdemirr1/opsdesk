from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from opsdesk.comments.models import (
    Comment,
    CommentCreationContext,
    CommentListRead,
    CommentPage,
)
from opsdesk.comments.services import (
    CommentBusyError,
    CommentClosedError,
    CommentContentError,
    CommentService,
)
from opsdesk.identity.models import User
from opsdesk.organizations.models import Organization, OrganizationMembership
from opsdesk.tickets.models import Ticket, TicketCreationContext
from opsdesk.tickets.read_models import TicketReadAccess
from opsdesk.tickets.repositories import TicketConcurrencyError
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
)

NOW = datetime(2026, 10, 29, tzinfo=UTC)
ACCESS = TicketCreationContext(
    Organization(10, "Demo", True),
    User(42, "demo@example.com", "hash", True),
    OrganizationMembership(40, 42, 10, "customer", True),
)
TICKET = Ticket(20, 10, 40, 40, None, "Issue", "Details", "open", "medium", NOW, NOW)
ARGS = dict(
    actor_user_id=42, organization_id=10, ticket_id=20, content=" text\r\nnext "
)


@pytest.fixture
def service():
    repo, transaction = Mock(), Mock()
    repo.lock_creation_context.return_value = CommentCreationContext(ACCESS, TICKET)
    repo.create.return_value = Comment(30, 10, 20, 40, "text\nnext", NOW)
    return CommentService(repo, transaction), repo, transaction


@pytest.mark.parametrize("role", ["customer", "agent", "admin", "owner"])
@pytest.mark.parametrize("status", ["open", "in_progress", "resolved"])
def test_author_derived_and_normalized_with_commit(service, role, status):
    subject, repo, tx = service
    access = replace(
        ACCESS, actor_membership=replace(ACCESS.actor_membership, role=role)
    )
    repo.lock_creation_context.return_value = CommentCreationContext(
        access, replace(TICKET, status=status)
    )
    assert subject.create(**ARGS).comment_id == 30
    inserted = repo.create.call_args.args[0]
    assert (
        inserted.organization_id,
        inserted.ticket_id,
        inserted.author_membership_id,
        inserted.content,
    ) == (10, 20, 40, "text\nnext")
    tx.commit.assert_called_once()
    tx.rollback.assert_not_called()


@pytest.mark.parametrize(
    "context,error",
    [
        (None, TicketOrganizationAccessDeniedError),
        (
            CommentCreationContext(replace(ACCESS, actor_user=None), TICKET),
            TicketActorUnavailableError,
        ),
        (
            CommentCreationContext(
                replace(ACCESS, actor_user=replace(ACCESS.actor_user, is_active=False)),
                TICKET,
            ),
            TicketActorUnavailableError,
        ),
        (
            CommentCreationContext(replace(ACCESS, actor_membership=None), TICKET),
            TicketOrganizationAccessDeniedError,
        ),
        (
            CommentCreationContext(
                replace(
                    ACCESS,
                    actor_membership=replace(ACCESS.actor_membership, is_active=False),
                ),
                TICKET,
            ),
            TicketOrganizationAccessDeniedError,
        ),
        (
            CommentCreationContext(
                replace(
                    ACCESS, organization=replace(ACCESS.organization, is_active=False)
                ),
                TICKET,
            ),
            TicketOrganizationSuspendedError,
        ),
        (CommentCreationContext(ACCESS, None), TicketNotFoundError),
        (
            CommentCreationContext(ACCESS, replace(TICKET, requester_membership_id=41)),
            TicketNotFoundError,
        ),
        (
            CommentCreationContext(ACCESS, replace(TICKET, status="closed")),
            CommentClosedError,
        ),
    ],
)
def test_denials_rollback_without_inserting(service, context, error):
    subject, repo, tx = service
    repo.lock_creation_context.return_value = context
    with pytest.raises(error):
        subject.create(**ARGS)
    repo.create.assert_not_called()
    tx.commit.assert_not_called()
    tx.rollback.assert_called_once()


@pytest.mark.parametrize("stage", ["lock_creation_context", "create", "commit"])
@pytest.mark.parametrize(
    "failure,expected",
    [(TicketConcurrencyError, CommentBusyError), (RuntimeError, RuntimeError)],
)
def test_failures_rollback_and_preserve_unexpected_errors(
    service, stage, failure, expected
):
    subject, repo, tx = service
    getattr(tx if stage == "commit" else repo, stage).side_effect = failure
    with pytest.raises(expected):
        subject.create(**ARGS)
    tx.rollback.assert_called_once()


def test_direct_service_invalid_content_rejected(service):
    subject, repo, tx = service
    with pytest.raises(CommentContentError):
        subject.create(**{**ARGS, "content": "\x00secret"})
    repo.lock_creation_context.assert_not_called()
    tx.rollback.assert_called_once()


@pytest.mark.parametrize(
    "access,visible,error",
    [
        (TicketReadAccess(False, True, True), True, TicketActorUnavailableError),
        (
            TicketReadAccess(True, False, True),
            True,
            TicketOrganizationAccessDeniedError,
        ),
        (TicketReadAccess(True, True, False), True, TicketOrganizationSuspendedError),
        (TicketReadAccess(True, True, True), False, TicketNotFoundError),
    ],
)
def test_read_access_checked_before_returning_page(service, access, visible, error):
    subject, repo, _ = service
    repo.list_for_actor.return_value = CommentListRead(
        access, visible, CommentPage((), 0, 20, 0)
    )
    with pytest.raises(error):
        subject.list_for_actor(
            actor_user_id=42, organization_id=10, ticket_id=20, limit=20, offset=0
        )

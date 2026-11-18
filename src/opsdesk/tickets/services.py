from typing import get_args

from opsdesk.tickets.models import NewTicket, Ticket, TicketStatus
from opsdesk.tickets.read_models import (
    TicketFilters,
    TicketList,
    TicketReadAccess,
    TicketStats,
)
from opsdesk.tickets.repositories import (
    TicketConcurrencyError,
    TicketCreationRepository,
    TicketReadRepository,
    TicketTransaction,
)


class TicketActorUnavailableError(Exception):
    pass


class TicketOrganizationAccessDeniedError(Exception):
    pass


class TicketOrganizationSuspendedError(Exception):
    pass


class TicketCreationBusyError(Exception):
    pass


class TicketCreationService:
    def __init__(
        self,
        repository: TicketCreationRepository,
        transaction: TicketTransaction,
    ) -> None:
        self._repository = repository
        self._transaction = transaction

    def create(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        title: str,
        description: str,
        priority: str,
    ) -> Ticket:
        try:
            context = self._repository.lock_creation_context(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
            )

            if context is None:
                raise TicketOrganizationAccessDeniedError

            if context.actor_user is None or not context.actor_user.is_active:
                raise TicketActorUnavailableError

            if (
                context.actor_membership is None
                or not context.actor_membership.is_active
            ):
                raise TicketOrganizationAccessDeniedError

            if not context.organization.is_active:
                raise TicketOrganizationSuspendedError

            ticket = self._repository.create(
                NewTicket(
                    organization_id=context.organization.organization_id,
                    requester_membership_id=(context.actor_membership.membership_id),
                    creator_membership_id=(context.actor_membership.membership_id),
                    title=title,
                    description=description,
                    priority=priority,
                )
            )

            self._transaction.commit()
        except TicketConcurrencyError:
            self._transaction.rollback()
            raise TicketCreationBusyError from None
        except Exception:
            self._transaction.rollback()
            raise

        return ticket


class TicketNotFoundError(Exception):
    pass


class TicketReadBusyError(Exception):
    pass


class TicketReadService:
    def __init__(self, repository: TicketReadRepository, stats_cache=None) -> None:
        self._repository = repository
        self._stats_cache = stats_cache

    @staticmethod
    def _check_access(access: TicketReadAccess) -> None:
        if not access.actor_active:
            raise TicketActorUnavailableError
        if not access.membership_active:
            raise TicketOrganizationAccessDeniedError
        if not access.organization_active:
            raise TicketOrganizationSuspendedError

    def list_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        filters: TicketFilters,
        limit: int,
        offset: int,
    ) -> TicketList:
        try:
            result = self._repository.list_for_actor(
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                filters=filters,
                limit=limit,
                offset=offset,
            )
        except TicketConcurrencyError:
            raise TicketReadBusyError from None
        self._check_access(result.access)
        return result.page

    def get_for_actor(
        self, *, actor_user_id: int, organization_id: int, ticket_id: int
    ) -> Ticket:
        try:
            result = self._repository.get_for_actor(
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                ticket_id=ticket_id,
            )
        except TicketConcurrencyError:
            raise TicketReadBusyError from None
        self._check_access(result.access)
        if result.ticket is None:
            raise TicketNotFoundError
        return result.ticket

    def stats_for_actor(
        self, *, actor_user_id: int, organization_id: int
    ) -> TicketStats:
        cache = self._stats_cache
        key = None
        writable = False
        try:
            if cache is not None:
                access = self._repository.stats_access_for_actor(
                    actor_user_id=actor_user_id, organization_id=organization_id
                )
                self._check_access(access.access)
                if access.scope is not None:
                    key = cache.key(actor_user_id, organization_id, access.scope)
                    hit, writable = cache.get(key)
                    if hit is not None:
                        return hit
            result = self._repository.stats_for_actor(
                actor_user_id=actor_user_id, organization_id=organization_id
            )
        except TicketConcurrencyError:
            raise TicketReadBusyError from None
        self._check_access(result.access)
        counts = {
            status: result.counts.get(status, 0) for status in get_args(TicketStatus)
        }
        stats = TicketStats(total=sum(counts.values()), by_status=counts)
        # Only cache under the scope observed with the aggregate itself.
        # A role change between the two SQL snapshots must not poison either key.
        if cache is not None and writable and result.scope is not None:
            result_key = cache.key(actor_user_id, organization_id, result.scope)
            if result_key == key:
                cache.put(key, stats)
        return stats

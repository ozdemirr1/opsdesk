from opsdesk.tickets.models import NewTicket, Ticket
from opsdesk.tickets.repositories import (
    TicketConcurrencyError,
    TicketCreationRepository,
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

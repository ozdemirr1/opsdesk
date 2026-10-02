from opsdesk.organizations.models import (
    NewOrganization,
    NewOrganizationMembership,
    OrganizationCreation,
)
from opsdesk.organizations.repositories import (
    OrganizationConcurrencyError,
    OrganizationCreationRepository,
    OrganizationTransaction,
)


class OrganizationActorUnavailableError(Exception):
    pass


class OrganizationCreationBusyError(Exception):
    pass


class OrganizationCreationService:
    def __init__(
        self,
        repository: OrganizationCreationRepository,
        transaction: OrganizationTransaction,
    ) -> None:
        self._repository = repository
        self._transaction = transaction

    def create(
        self,
        *,
        actor_user_id: int,
        name: str,
    ) -> OrganizationCreation:
        try:
            actor = self._repository.lock_user_for_organization_creation(actor_user_id)

            if actor is None or not actor.is_active:
                raise OrganizationActorUnavailableError

            organization = self._repository.create_organization(
                NewOrganization(name=name)
            )

            own_membership = self._repository.create_membership(
                NewOrganizationMembership(
                    user_id=actor.user_id,
                    organization_id=organization.organization_id,
                    role="owner",
                )
            )

            self._transaction.commit()
        except OrganizationConcurrencyError:
            self._transaction.rollback()
            raise OrganizationCreationBusyError from None
        except Exception:
            self._transaction.rollback()
            raise

        return OrganizationCreation(
            organization=organization,
            own_membership=own_membership,
        )

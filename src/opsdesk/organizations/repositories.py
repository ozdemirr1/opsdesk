from typing import Protocol

from opsdesk.identity.models import User
from opsdesk.organizations.models import (
    NewOrganization,
    NewOrganizationMembership,
    Organization,
    OrganizationMembership,
)


class OrganizationConcurrencyError(Exception):
    pass


class OrganizationCreationRepository(Protocol):
    def lock_user_for_organization_creation(
        self,
        user_id: int,
    ) -> User | None: ...

    def create_organization(
        self,
        new_organization: NewOrganization,
    ) -> Organization: ...

    def create_membership(
        self,
        new_membership: NewOrganizationMembership,
    ) -> OrganizationMembership: ...


class OrganizationTransaction(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...

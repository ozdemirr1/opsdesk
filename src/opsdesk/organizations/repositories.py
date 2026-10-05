from typing import Protocol

from opsdesk.identity.models import User
from opsdesk.organizations.models import (
    NewOrganization,
    NewOrganizationMembership,
    Organization,
    OrganizationList,
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


class OrganizationReadRepository(Protocol):
    def list_for_user(
        self,
        *,
        user_id: int,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> OrganizationList: ...

    def get_for_user(
        self,
        *,
        user_id: int,
        organization_id: int,
    ) -> Organization | None: ...

from dataclasses import dataclass
from typing import Literal

OrganizationRole = Literal[
    "owner",
    "admin",
    "agent",
    "customer",
]


@dataclass(frozen=True, slots=True)
class NewOrganization:
    name: str


@dataclass(frozen=True, slots=True)
class Organization:
    organization_id: int
    name: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class NewOrganizationMembership:
    user_id: int
    organization_id: int
    role: OrganizationRole


@dataclass(frozen=True, slots=True)
class OrganizationMembership:
    membership_id: int
    user_id: int
    organization_id: int
    role: OrganizationRole
    is_active: bool


@dataclass(frozen=True, slots=True)
class OrganizationCreation:
    organization: Organization
    own_membership: OrganizationMembership

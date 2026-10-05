import pytest

from opsdesk.organizations.models import (
    Organization,
    OrganizationList,
    OrganizationListItem,
    OrganizationMembership,
)
from opsdesk.organizations.services import (
    OrganizationAccessDeniedError,
    OrganizationReadService,
)


def build_organization(
    *,
    organization_id: int = 100,
    is_active: bool = True,
) -> Organization:
    return Organization(
        organization_id=organization_id,
        name=f"Organization {organization_id}",
        is_active=is_active,
    )


def build_list_result() -> OrganizationList:
    organization = build_organization()

    return OrganizationList(
        items=(
            OrganizationListItem(
                organization=organization,
                own_membership=OrganizationMembership(
                    membership_id=200,
                    user_id=42,
                    organization_id=organization.organization_id,
                    role="agent",
                    is_active=True,
                ),
            ),
        ),
        total_count=1,
        limit=20,
        offset=0,
    )


class FakeOrganizationReadRepository:
    def __init__(
        self,
        *,
        list_result: OrganizationList | None = None,
        detail_result: Organization | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.list_result = list_result or OrganizationList(
            items=(),
            total_count=0,
            limit=20,
            offset=0,
        )
        self.detail_result = detail_result
        self.failure = failure
        self.list_calls: list[dict[str, object]] = []
        self.detail_calls: list[dict[str, int]] = []

    def list_for_user(
        self,
        *,
        user_id: int,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> OrganizationList:
        self.list_calls.append(
            {
                "user_id": user_id,
                "is_active": is_active,
                "limit": limit,
                "offset": offset,
            }
        )

        if self.failure is not None:
            raise self.failure

        return self.list_result

    def get_for_user(
        self,
        *,
        user_id: int,
        organization_id: int,
    ) -> Organization | None:
        self.detail_calls.append(
            {
                "user_id": user_id,
                "organization_id": organization_id,
            }
        )

        if self.failure is not None:
            raise self.failure

        return self.detail_result


@pytest.mark.parametrize(
    "is_active",
    [
        None,
        True,
        False,
    ],
)
def test_list_forwards_actor_scope_filter_and_pagination(is_active):
    result = build_list_result()
    repository = FakeOrganizationReadRepository(list_result=result)
    service = OrganizationReadService(repository)

    returned = service.list_for_actor(
        actor_user_id=42,
        is_active=is_active,
        limit=20,
        offset=10,
    )

    assert returned is result
    assert repository.list_calls == [
        {
            "user_id": 42,
            "is_active": is_active,
            "limit": 20,
            "offset": 10,
        }
    ]


@pytest.mark.parametrize(
    "is_active",
    [
        True,
        False,
    ],
)
def test_detail_returns_accessible_active_or_suspended_organization(
    is_active,
):
    organization = build_organization(is_active=is_active)
    repository = FakeOrganizationReadRepository(
        detail_result=organization,
    )
    service = OrganizationReadService(repository)

    returned = service.get_for_actor(
        actor_user_id=42,
        organization_id=100,
    )

    assert returned is organization
    assert repository.detail_calls == [
        {
            "user_id": 42,
            "organization_id": 100,
        }
    ]


def test_missing_or_inaccessible_detail_uses_same_domain_error():
    repository = FakeOrganizationReadRepository(detail_result=None)
    service = OrganizationReadService(repository)

    with pytest.raises(OrganizationAccessDeniedError):
        service.get_for_actor(
            actor_user_id=42,
            organization_id=999,
        )


def test_unexpected_repository_failure_is_not_hidden():
    repository = FakeOrganizationReadRepository(
        failure=RuntimeError("Synthetic repository failure"),
    )
    service = OrganizationReadService(repository)

    with pytest.raises(
        RuntimeError,
        match="^Synthetic repository failure$",
    ):
        service.list_for_actor(
            actor_user_id=42,
            is_active=None,
            limit=20,
            offset=0,
        )

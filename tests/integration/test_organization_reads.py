from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from opsdesk.config import Settings
from opsdesk.db.models import (
    OrganizationMembershipRow,
    OrganizationRow,
    UserRow,
)
from opsdesk.db.repositories.organizations import (
    SqlAlchemyOrganizationRepository,
)
from opsdesk.db.session import session_scope
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import AccessTokenIssuer
from opsdesk.main import create_app

SECRET = "a" * 64
FIXED_NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

ACCESS_DENIED_RESPONSE = {
    "error": {
        "code": "organization_access_denied",
        "message": "Organization access denied.",
        "details": [],
    }
}


def build_app(factory):
    return create_app(
        Settings(environment="test"),
        session_factory=factory,
        token_settings=TokenSettings(secret=SECRET),
        token_clock=lambda: FIXED_NOW,
    )


def issue_token(user_id: int) -> str:
    return AccessTokenIssuer(
        TokenSettings(secret=SECRET),
        clock=lambda: FIXED_NOW,
    ).issue(user_id)


def bearer_headers(user_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {issue_token(user_id)}",
    }


def create_user(
    factory,
    *,
    email: str,
    is_active: bool = True,
) -> int:
    with session_scope(factory) as session:
        user = UserRow(
            email=email,
            password_hash="synthetic-password-hash",
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        return user.user_id


def create_organization_with_membership(
    factory,
    *,
    user_id: int,
    name: str,
    organization_is_active: bool = True,
    membership_is_active: bool = True,
    role: str = "agent",
) -> tuple[int, int]:
    with session_scope(factory) as session:
        organization = OrganizationRow(
            name=name,
            is_active=organization_is_active,
        )
        session.add(organization)
        session.flush()

        membership = OrganizationMembershipRow(
            user_id=user_id,
            organization_id=organization.organization_id,
            role=role,
            is_active=membership_is_active,
        )
        session.add(membership)
        session.commit()

        return (
            organization.organization_id,
            membership.membership_id,
        )


def read_counts(factory) -> tuple[int, int, int]:
    with session_scope(factory) as session:
        return (
            session.scalar(select(func.count()).select_from(UserRow)),
            session.scalar(select(func.count()).select_from(OrganizationRow)),
            session.scalar(select(func.count()).select_from(OrganizationMembershipRow)),
        )


@pytest.mark.integration
def test_list_exposes_only_active_own_memberships_without_writes(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="organization-reader@example.com",
        )
        foreign_user_id = create_user(
            factory,
            email="foreign-reader@example.com",
        )

        active_id, active_membership_id = create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Active Organization",
            organization_is_active=True,
            role="owner",
        )
        suspended_id, suspended_membership_id = create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Suspended Organization",
            organization_is_active=False,
            role="customer",
        )
        create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Inactive Membership",
            membership_is_active=False,
        )
        create_organization_with_membership(
            factory,
            user_id=foreign_user_id,
            name="Foreign Organization",
        )

        counts_before = read_counts(factory)
        app = build_app(factory)

        with TestClient(app) as client:
            response = client.get(
                "/organizations",
                headers=bearer_headers(actor_id),
            )

        assert response.status_code == 200
        assert response.json() == {
            "items": [
                {
                    "organization": {
                        "organization_id": active_id,
                        "name": "Active Organization",
                        "is_active": True,
                    },
                    "own_membership": {
                        "membership_id": active_membership_id,
                        "organization_id": active_id,
                        "role": "owner",
                        "is_active": True,
                    },
                },
                {
                    "organization": {
                        "organization_id": suspended_id,
                        "name": "Suspended Organization",
                        "is_active": False,
                    },
                    "own_membership": {
                        "membership_id": suspended_membership_id,
                        "organization_id": suspended_id,
                        "role": "customer",
                        "is_active": True,
                    },
                },
            ],
            "total_count": 2,
            "limit": 20,
            "offset": 0,
        }
        assert "user_id" not in response.text
        assert "foreign-reader@example.com" not in response.text
        assert read_counts(factory) == counts_before


@pytest.mark.integration
@pytest.mark.parametrize(
    ("filter_value", "expected_active"),
    [
        ("true", True),
        ("false", False),
    ],
)
def test_list_filter_narrows_only_authorized_scope(
    identity_scope,
    filter_value,
    expected_active,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email=f"filter-{filter_value}@example.com",
        )

        expected_id, _ = create_organization_with_membership(
            factory,
            user_id=actor_id,
            name=f"Expected {filter_value}",
            organization_is_active=expected_active,
        )
        create_organization_with_membership(
            factory,
            user_id=actor_id,
            name=f"Excluded {filter_value}",
            organization_is_active=not expected_active,
        )

        app = build_app(factory)

        with TestClient(app) as client:
            response = client.get(
                "/organizations",
                params={
                    "is_active": filter_value,
                },
                headers=bearer_headers(actor_id),
            )

        assert response.status_code == 200
        payload = response.json()

        assert payload["total_count"] == 1
        assert len(payload["items"]) == 1
        assert payload["items"][0]["organization"]["organization_id"] == expected_id
        assert payload["items"][0]["organization"]["is_active"] is expected_active


@pytest.mark.integration
def test_list_pagination_preserves_total_and_stable_order(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="pagination@example.com",
        )

        organization_ids = [
            create_organization_with_membership(
                factory,
                user_id=actor_id,
                name=f"Organization {index}",
            )[0]
            for index in range(3)
        ]

        app = build_app(factory)

        with TestClient(app) as client:
            page_response = client.get(
                "/organizations",
                params={
                    "limit": "1",
                    "offset": "1",
                },
                headers=bearer_headers(actor_id),
            )
            beyond_response = client.get(
                "/organizations",
                params={
                    "limit": "2",
                    "offset": "99",
                },
                headers=bearer_headers(actor_id),
            )

        assert page_response.status_code == 200
        assert page_response.json()["total_count"] == 3
        assert page_response.json()["limit"] == 1
        assert page_response.json()["offset"] == 1
        assert [
            item["organization"]["organization_id"]
            for item in page_response.json()["items"]
        ] == [organization_ids[1]]

        assert beyond_response.status_code == 200
        assert beyond_response.json() == {
            "items": [],
            "total_count": 3,
            "limit": 2,
            "offset": 99,
        }


@pytest.mark.integration
def test_empty_authorized_scope_returns_empty_collection(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="empty-organizations@example.com",
        )
        app = build_app(factory)

        with TestClient(app) as client:
            response = client.get(
                "/organizations",
                headers=bearer_headers(actor_id),
            )

        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total_count": 0,
            "limit": 20,
            "offset": 0,
        }


@pytest.mark.integration
def test_detail_exposes_active_and_suspended_organizations(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="detail-reader@example.com",
        )

        active_id, _ = create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Active Detail",
            organization_is_active=True,
        )
        suspended_id, _ = create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Suspended Detail",
            organization_is_active=False,
        )

        app = build_app(factory)

        with TestClient(app) as client:
            active_response = client.get(
                f"/organizations/{active_id}",
                headers=bearer_headers(actor_id),
            )
            suspended_response = client.get(
                f"/organizations/{suspended_id}",
                headers=bearer_headers(actor_id),
            )

        assert active_response.status_code == 200
        assert active_response.json() == {
            "organization_id": active_id,
            "name": "Active Detail",
            "is_active": True,
        }

        assert suspended_response.status_code == 200
        assert suspended_response.json() == {
            "organization_id": suspended_id,
            "name": "Suspended Detail",
            "is_active": False,
        }


@pytest.mark.integration
def test_missing_foreign_and_inactive_membership_details_share_403(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="denied-reader@example.com",
        )
        foreign_user_id = create_user(
            factory,
            email="foreign-owner@example.com",
        )

        foreign_id, _ = create_organization_with_membership(
            factory,
            user_id=foreign_user_id,
            name="Foreign Detail",
        )
        inactive_organization_id, _ = create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Inactive Membership Detail",
            membership_is_active=False,
        )

        app = build_app(factory)

        with TestClient(app) as client:
            responses = [
                client.get(
                    "/organizations/9223372036854775807",
                    headers=bearer_headers(actor_id),
                ),
                client.get(
                    f"/organizations/{foreign_id}",
                    headers=bearer_headers(actor_id),
                ),
                client.get(
                    f"/organizations/{inactive_organization_id}",
                    headers=bearer_headers(actor_id),
                ),
            ]

        for response in responses:
            assert response.status_code == 403
            assert response.json() == ACCESS_DENIED_RESPONSE


@pytest.mark.integration
def test_inactive_user_cannot_read_organizations(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="inactive-reader@example.com",
            is_active=False,
        )
        create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Hidden From Inactive User",
        )

        app = build_app(factory)

        with TestClient(app) as client:
            response = client.get(
                "/organizations",
                headers=bearer_headers(actor_id),
            )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"


@pytest.mark.integration
def test_list_count_and_page_use_one_unlocked_database_statement(
    identity_scope,
    integration_engine,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="single-statement@example.com",
        )
        create_organization_with_membership(
            factory,
            user_id=actor_id,
            name="Single Statement Organization",
        )

        observed_statements: list[str] = []

        def record_statement(
            connection,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ):
            if "visible_organizations" in statement:
                observed_statements.append(statement)

        event.listen(
            integration_engine,
            "before_cursor_execute",
            record_statement,
        )

        try:
            with session_scope(factory) as session:
                result = SqlAlchemyOrganizationRepository(session).list_for_user(
                    user_id=actor_id,
                    is_active=None,
                    limit=20,
                    offset=99,
                )
        finally:
            event.remove(
                integration_engine,
                "before_cursor_execute",
                record_statement,
            )

        assert result.items == ()
        assert result.total_count == 1
        assert len(observed_statements) == 1
        assert "FOR UPDATE" not in observed_statements[0].upper()
        assert "FOR SHARE" not in observed_statements[0].upper()

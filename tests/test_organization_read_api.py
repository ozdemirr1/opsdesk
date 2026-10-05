from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.main import create_app
from opsdesk.organizations.dependencies import (
    get_organization_read_service,
)
from opsdesk.organizations.models import (
    Organization,
    OrganizationList,
    OrganizationListItem,
    OrganizationMembership,
)
from opsdesk.organizations.services import (
    OrganizationAccessDeniedError,
)

SECRET = "synthetic-private-organization-marker"


def build_current_user() -> User:
    return User(
        user_id=42,
        email="actor@example.com",
        password_hash="private-password-hash",
        is_active=True,
    )


def build_list_result() -> OrganizationList:
    return OrganizationList(
        items=(
            OrganizationListItem(
                organization=Organization(
                    organization_id=100,
                    name="Active Organization",
                    is_active=True,
                ),
                own_membership=OrganizationMembership(
                    membership_id=200,
                    user_id=42,
                    organization_id=100,
                    role="owner",
                    is_active=True,
                ),
            ),
            OrganizationListItem(
                organization=Organization(
                    organization_id=101,
                    name="Suspended Organization",
                    is_active=False,
                ),
                own_membership=OrganizationMembership(
                    membership_id=201,
                    user_id=42,
                    organization_id=101,
                    role="agent",
                    is_active=True,
                ),
            ),
        ),
        total_count=2,
        limit=20,
        offset=0,
    )


class RecordingOrganizationReadService:
    def __init__(
        self,
        *,
        list_result: OrganizationList | None = None,
        detail_result: Organization | None = None,
        error: Exception | None = None,
    ) -> None:
        self.list_result = list_result or OrganizationList(
            items=(),
            total_count=0,
            limit=20,
            offset=0,
        )
        self.detail_result = detail_result
        self.error = error
        self.list_calls: list[dict[str, object]] = []
        self.detail_calls: list[dict[str, int]] = []

    def list_for_actor(
        self,
        *,
        actor_user_id: int,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> OrganizationList:
        self.list_calls.append(
            {
                "actor_user_id": actor_user_id,
                "is_active": is_active,
                "limit": limit,
                "offset": offset,
            }
        )

        if self.error is not None:
            raise self.error

        return self.list_result

    def get_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
    ) -> Organization:
        self.detail_calls.append(
            {
                "actor_user_id": actor_user_id,
                "organization_id": organization_id,
            }
        )

        if self.error is not None:
            raise self.error

        if self.detail_result is None:
            raise OrganizationAccessDeniedError

        return self.detail_result


def build_client(
    service: RecordingOrganizationReadService,
    *,
    authenticated: bool = True,
) -> TestClient:
    app = create_app(Settings(environment="test"))

    app.dependency_overrides[get_organization_read_service] = lambda: service

    if authenticated:
        app.dependency_overrides[get_current_user] = build_current_user

    return TestClient(app)


def test_list_returns_reviewed_membership_scoped_projection():
    service = RecordingOrganizationReadService(
        list_result=build_list_result(),
    )

    with build_client(service) as client:
        response = client.get("/organizations")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "organization": {
                    "organization_id": 100,
                    "name": "Active Organization",
                    "is_active": True,
                },
                "own_membership": {
                    "membership_id": 200,
                    "organization_id": 100,
                    "role": "owner",
                    "is_active": True,
                },
            },
            {
                "organization": {
                    "organization_id": 101,
                    "name": "Suspended Organization",
                    "is_active": False,
                },
                "own_membership": {
                    "membership_id": 201,
                    "organization_id": 101,
                    "role": "agent",
                    "is_active": True,
                },
            },
        ],
        "total_count": 2,
        "limit": 20,
        "offset": 0,
    }
    assert service.list_calls == [
        {
            "actor_user_id": 42,
            "is_active": None,
            "limit": 20,
            "offset": 0,
        }
    ]
    assert "user_id" not in response.text
    assert UUID(response.headers["x-request-id"]).version == 4


def test_filter_and_pagination_are_forwarded():
    service = RecordingOrganizationReadService()

    with build_client(service) as client:
        response = client.get(
            "/organizations",
            params={
                "is_active": "false",
                "limit": "10",
                "offset": "30",
            },
        )

    assert response.status_code == 200
    assert service.list_calls == [
        {
            "actor_user_id": 42,
            "is_active": False,
            "limit": 10,
            "offset": 30,
        }
    ]


@pytest.mark.parametrize(
    ("query", "expected_field"),
    [
        ("is_active=True", "query.is_active"),
        ("is_active=1", "query.is_active"),
        ("limit=0", "query.limit"),
        ("limit=101", "query.limit"),
        ("offset=-1", "query.offset"),
        ("limit=1.5", "query.limit"),
    ],
)
def test_invalid_query_is_rejected_before_service(
    query,
    expected_field,
):
    service = RecordingOrganizationReadService()

    with build_client(service) as client:
        response = client.get(f"/organizations?{query}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"][0]["field"] == expected_field
    assert service.list_calls == []


def test_repeated_query_key_is_rejected():
    service = RecordingOrganizationReadService()

    with build_client(service) as client:
        response = client.get(
            "/organizations",
            params=[
                ("limit", "10"),
                ("limit", "20"),
            ],
        )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "query.limit"
    assert service.list_calls == []


def test_unknown_query_key_is_not_reflected():
    service = RecordingOrganizationReadService()

    with build_client(service) as client:
        response = client.get(
            "/organizations",
            params={
                SECRET: SECRET,
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "query"
    assert SECRET not in response.text
    assert service.list_calls == []


def test_missing_authentication_is_rejected_before_read():
    service = RecordingOrganizationReadService()

    with build_client(
        service,
        authenticated=False,
    ) as client:
        response = client.get("/organizations")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert service.list_calls == []


@pytest.mark.parametrize(
    "is_active",
    [
        True,
        False,
    ],
)
def test_detail_returns_active_or_suspended_organization(is_active):
    service = RecordingOrganizationReadService(
        detail_result=Organization(
            organization_id=100,
            name="Acme",
            is_active=is_active,
        )
    )

    with build_client(service) as client:
        response = client.get("/organizations/100")

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": 100,
        "name": "Acme",
        "is_active": is_active,
    }
    assert service.detail_calls == [
        {
            "actor_user_id": 42,
            "organization_id": 100,
        }
    ]


def test_missing_or_inaccessible_detail_returns_same_403():
    service = RecordingOrganizationReadService(
        error=OrganizationAccessDeniedError(),
    )

    with build_client(service) as client:
        response = client.get("/organizations/999")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "organization_access_denied",
            "message": "Organization access denied.",
            "details": [],
        }
    }


def test_invalid_detail_identifier_never_calls_service():
    service = RecordingOrganizationReadService()

    with build_client(service) as client:
        response = client.get("/organizations/0")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == ("path.organization_id")
    assert service.detail_calls == []


def test_unexpected_failure_remains_safe_internal_error():
    service = RecordingOrganizationReadService(
        error=RuntimeError(SECRET),
    )

    with build_client(service) as client:
        response = client.get("/organizations")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert SECRET not in response.text

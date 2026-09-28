import pytest

from opsdesk.identity.models import User
from opsdesk.identity.services import (
    InvalidCredentialsError,
    LoginService,
)


class FakeUserReader:
    def __init__(
        self,
        events: list[str],
        user: User | None = None,
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.user = user
        self.error = error
        self.received_email = None

    def get_by_email(self, email: str) -> User | None:
        self.events.append("lookup")
        self.received_email = email

        if self.error is not None:
            raise self.error

        return self.user


class FakePasswordHasher:
    def __init__(
        self,
        events: list[str],
        result: bool,
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def verify_password(
        self,
        plain_password: str,
        password_hash: str,
    ) -> bool:
        self.events.append("verify")
        self.calls.append((plain_password, password_hash))

        if self.error is not None:
            raise self.error

        return self.result


class FakeTokenIssuer:
    def __init__(
        self,
        events: list[str],
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.error = error
        self.user_ids: list[int] = []

    def issue(self, user_id: int) -> str:
        self.events.append("issue")
        self.user_ids.append(user_id)

        if self.error is not None:
            raise self.error

        return "signed-access-token"


def build_user(*, is_active: bool = True) -> User:
    return User(
        user_id=42,
        email="user@example.com",
        password_hash="stored-password-hash",
        is_active=is_active,
    )


def build_service(
    *,
    user: User | None,
    password_matches: bool,
    repository_error: Exception | None = None,
    verification_error: Exception | None = None,
    issuer_error: Exception | None = None,
):
    events: list[str] = []
    repository = FakeUserReader(
        events,
        user=user,
        error=repository_error,
    )
    hasher = FakePasswordHasher(
        events,
        result=password_matches,
        error=verification_error,
    )
    issuer = FakeTokenIssuer(
        events,
        error=issuer_error,
    )
    service = LoginService(
        repository=repository,
        password_hasher=hasher,
        token_issuer=issuer,
        dummy_password_hash="dummy-password-hash",
    )
    return service, repository, hasher, issuer, events


def test_login_issues_token_only_after_successful_verification():
    service, repository, hasher, issuer, events = build_service(
        user=build_user(),
        password_matches=True,
    )

    token = service.login(
        email="user@example.com",
        plain_password="submitted password",
    )

    assert token == "signed-access-token"
    assert repository.received_email == "user@example.com"
    assert hasher.calls == [("submitted password", "stored-password-hash")]
    assert issuer.user_ids == [42]
    assert events == ["lookup", "verify", "issue"]


def test_unknown_email_verifies_dummy_hash_before_rejection():
    service, _, hasher, issuer, events = build_service(
        user=None,
        password_matches=False,
    )

    with pytest.raises(InvalidCredentialsError):
        service.login(
            email="missing@example.com",
            plain_password="submitted password",
        )

    assert hasher.calls == [("submitted password", "dummy-password-hash")]
    assert issuer.user_ids == []
    assert events == ["lookup", "verify"]


@pytest.mark.parametrize(
    ("user", "password_matches"),
    [
        (build_user(), False),
        (build_user(is_active=False), True),
        (build_user(is_active=False), False),
    ],
)
def test_invalid_credentials_never_issue_token(
    user,
    password_matches,
):
    service, _, _, issuer, events = build_service(
        user=user,
        password_matches=password_matches,
    )

    with pytest.raises(InvalidCredentialsError):
        service.login(
            email="user@example.com",
            plain_password="submitted password",
        )

    assert issuer.user_ids == []
    assert events == ["lookup", "verify"]


def test_repository_failure_is_not_disguised_as_invalid_credentials():
    service, _, hasher, issuer, events = build_service(
        user=None,
        password_matches=False,
        repository_error=RuntimeError("Synthetic repository failure"),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^Synthetic repository failure$",
    ):
        service.login(
            email="user@example.com",
            plain_password="submitted password",
        )

    assert hasher.calls == []
    assert issuer.user_ids == []
    assert events == ["lookup"]


def test_password_verification_failure_is_not_disguised():
    service, _, _, issuer, events = build_service(
        user=build_user(),
        password_matches=False,
        verification_error=RuntimeError("Synthetic verification failure"),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^Synthetic verification failure$",
    ):
        service.login(
            email="user@example.com",
            plain_password="submitted password",
        )

    assert issuer.user_ids == []
    assert events == ["lookup", "verify"]


def test_token_signing_failure_produces_no_success():
    service, _, _, issuer, events = build_service(
        user=build_user(),
        password_matches=True,
        issuer_error=RuntimeError("Synthetic signing failure"),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^Synthetic signing failure$",
    ):
        service.login(
            email="user@example.com",
            plain_password="submitted password",
        )

    assert issuer.user_ids == [42]
    assert events == ["lookup", "verify", "issue"]

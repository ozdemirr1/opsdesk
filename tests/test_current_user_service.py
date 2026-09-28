import pytest

from opsdesk.identity.models import User
from opsdesk.identity.services import (
    CurrentUserService,
    CurrentUserUnavailableError,
)


class FakeUserByIdReader:
    def __init__(
        self,
        *,
        user: User | None = None,
        error: Exception | None = None,
    ) -> None:
        self.user = user
        self.error = error
        self.user_ids: list[int] = []

    def get_by_id(self, user_id: int) -> User | None:
        self.user_ids.append(user_id)

        if self.error is not None:
            raise self.error

        return self.user


def build_user(*, is_active: bool = True) -> User:
    return User(
        user_id=42,
        email="current@example.com",
        password_hash="stored-password-hash",
        is_active=is_active,
    )


def test_current_user_service_returns_active_persisted_user():
    repository = FakeUserByIdReader(user=build_user())
    service = CurrentUserService(repository)

    user = service.resolve(42)

    assert user == build_user()
    assert repository.user_ids == [42]


@pytest.mark.parametrize(
    "user",
    [
        None,
        build_user(is_active=False),
    ],
)
def test_missing_and_inactive_users_share_authentication_failure(user):
    repository = FakeUserByIdReader(user=user)
    service = CurrentUserService(repository)

    with pytest.raises(CurrentUserUnavailableError):
        service.resolve(42)

    assert repository.user_ids == [42]


def test_database_failure_is_not_disguised_as_authentication_failure():
    repository = FakeUserByIdReader(
        error=RuntimeError("Synthetic database failure"),
    )
    service = CurrentUserService(repository)

    with pytest.raises(
        RuntimeError,
        match=r"^Synthetic database failure$",
    ):
        service.resolve(42)

    assert repository.user_ids == [42]

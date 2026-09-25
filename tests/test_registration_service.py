import pytest

from opsdesk.identity.models import NewUser, User
from opsdesk.identity.repositories import UserEmailConflictError
from opsdesk.identity.services import EmailAlreadyExistsError, RegistrationService


class FakePasswordHasher:
    def __init__(self, events: list[str], fail_hash: bool = False):
        self.events = events
        self.fail_hash = fail_hash
        self.received_plain = None

    def hash_password(self, plain_password: str) -> str:
        self.events.append("hash")
        if self.fail_hash:
            raise RuntimeError("Synthetic hash failure")
        self.received_plain = plain_password
        return "synthetic_password_hash"


class FakeUserRepository:
    def __init__(
        self,
        events: list[str],
        conflict: bool = False,
        unknown_error: bool = False,
    ):
        self.events = events
        self.conflict = conflict
        self.unknown_error = unknown_error
        self.received_new_user = None

    def create(self, new_user: NewUser) -> User:
        self.events.append("create")
        self.received_new_user = new_user

        if self.conflict:
            raise UserEmailConflictError()
        if self.unknown_error:
            raise RuntimeError("Synthetic DB error")

        return User(
            user_id=42,
            email=new_user.email,
            password_hash=new_user.password_hash,
            is_active=True,
        )


class FakeTransaction:
    def __init__(self, events: list[str], fail_commit: bool = False):
        self.events = events
        self.fail_commit = fail_commit

    def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit:
            raise RuntimeError("Synthetic commit failure")

    def rollback(self) -> None:
        self.events.append("rollback")


def test_registration_success_hashes_plain_password_and_commits():
    events: list[str] = []
    hasher = FakePasswordHasher(events)
    repo = FakeUserRepository(events)
    tx = FakeTransaction(events)
    service = RegistrationService(repo, tx, hasher)

    plain_password = "my_secure_password"
    user = service.register_user(
        email="test@example.com", plain_password=plain_password
    )

    assert hasher.received_plain == plain_password
    assert repo.received_new_user.password_hash == "synthetic_password_hash"
    assert user.user_id == 42
    assert events == ["hash", "create", "commit"]


def test_email_conflict_rolls_back_and_raises_specific_error():
    events: list[str] = []
    hasher = FakePasswordHasher(events)
    repo = FakeUserRepository(events, conflict=True)
    tx = FakeTransaction(events)
    service = RegistrationService(repo, tx, hasher)

    with pytest.raises(EmailAlreadyExistsError):
        service.register_user(email="test@example.com", plain_password="pwd")

    assert events == ["hash", "create", "rollback"]


def test_unknown_repository_error_rolls_back_and_reraises():
    events: list[str] = []
    hasher = FakePasswordHasher(events)
    repo = FakeUserRepository(events, unknown_error=True)
    tx = FakeTransaction(events)
    service = RegistrationService(repo, tx, hasher)

    with pytest.raises(RuntimeError, match="^Synthetic DB error$"):
        service.register_user(email="test@example.com", plain_password="pwd")

    assert events == ["hash", "create", "rollback"]


def test_commit_failure_rolls_back_and_reraises():
    events: list[str] = []
    hasher = FakePasswordHasher(events)
    repo = FakeUserRepository(events)
    tx = FakeTransaction(events, fail_commit=True)
    service = RegistrationService(repo, tx, hasher)

    with pytest.raises(RuntimeError, match="^Synthetic commit failure$"):
        service.register_user(email="test@example.com", plain_password="pwd")

    assert events == ["hash", "create", "commit", "rollback"]


def test_hash_failure_halts_execution_before_database_interaction():
    events: list[str] = []
    hasher = FakePasswordHasher(events, fail_hash=True)
    repo = FakeUserRepository(events)
    tx = FakeTransaction(events)
    service = RegistrationService(repo, tx, hasher)

    with pytest.raises(RuntimeError, match="^Synthetic hash failure$"):
        service.register_user(email="test@example.com", plain_password="pwd")

    assert events == ["hash"]

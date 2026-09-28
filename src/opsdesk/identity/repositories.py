from typing import Protocol

from opsdesk.identity.models import NewUser, User


class UserEmailConflictError(Exception):
    pass


class UserReader(Protocol):
    def get_by_email(self, email: str) -> User | None: ...


class UserRepository(UserReader, Protocol):
    def create(self, new_user: NewUser) -> User: ...


class Transaction(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class UserByIdReader(Protocol):
    def get_by_id(self, user_id: int) -> User | None: ...

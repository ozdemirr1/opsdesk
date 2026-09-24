from typing import Protocol

from opsdesk.identity.models import NewUser, User


class UserEmailConflictError(Exception):
    pass


class UserRepository(Protocol):
    def create(self, new_user: NewUser) -> User: ...


class Transaction(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...

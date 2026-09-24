from typing import Protocol

from opsdesk.identity.models import NewUser, User
from opsdesk.identity.repositories import (
    Transaction,
    UserEmailConflictError,
    UserRepository,
)


class PasswordHashing(Protocol):
    def hash_password(self, plain_password: str) -> str: ...


class EmailAlreadyExistsError(Exception):
    pass


class RegistrationService:
    def __init__(
        self,
        repository: UserRepository,
        transaction: Transaction,
        password_hasher: PasswordHashing,
    ) -> None:
        self._repository = repository
        self._transaction = transaction
        self._password_hasher = password_hasher

    def register_user(
        self,
        *,
        email: str,
        plain_password: str,
    ) -> User:
        password_hash = self._password_hasher.hash_password(plain_password)

        new_user = NewUser(
            email=email,
            password_hash=password_hash,
        )

        try:
            user = self._repository.create(new_user)
            self._transaction.commit()
        except UserEmailConflictError:
            self._transaction.rollback()
            raise EmailAlreadyExistsError from None
        except Exception:
            self._transaction.rollback()
            raise

        return user

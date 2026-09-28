from typing import Protocol

from opsdesk.identity.models import NewUser, User
from opsdesk.identity.repositories import (
    Transaction,
    UserByIdReader,
    UserEmailConflictError,
    UserReader,
    UserRepository,
)


class PasswordHashing(Protocol):
    def hash_password(self, plain_password: str) -> str: ...

    def verify_password(
        self,
        plain_password: str,
        password_hash: str,
    ) -> bool: ...


class TokenIssuing(Protocol):
    def issue(self, user_id: int) -> str: ...


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


class InvalidCredentialsError(Exception):
    pass


class LoginService:
    def __init__(
        self,
        repository: UserReader,
        password_hasher: PasswordHashing,
        token_issuer: TokenIssuing,
        dummy_password_hash: str,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._token_issuer = token_issuer
        self._dummy_password_hash = dummy_password_hash

    def login(
        self,
        *,
        email: str,
        plain_password: str,
    ) -> str:
        user = self._repository.get_by_email(email)

        password_hash = (
            user.password_hash if user is not None else self._dummy_password_hash
        )

        password_matches = self._password_hasher.verify_password(
            plain_password,
            password_hash,
        )

        if user is None or not password_matches or not user.is_active:
            raise InvalidCredentialsError

        return self._token_issuer.issue(user.user_id)


class CurrentUserUnavailableError(Exception):
    pass


class CurrentUserService:
    def __init__(
        self,
        repository: UserByIdReader,
    ) -> None:
        self._repository = repository

    def resolve(self, user_id: int) -> User:
        user = self._repository.get_by_id(user_id)

        if user is None or not user.is_active:
            raise CurrentUserUnavailableError

        return user

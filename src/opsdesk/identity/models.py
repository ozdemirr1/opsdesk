from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NewUser:
    email: str
    password_hash: str


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    email: str
    password_hash: str
    is_active: bool

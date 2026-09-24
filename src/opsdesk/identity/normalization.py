import unicodedata

from email_validator import EmailNotValidError, validate_email

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 254


def normalize_email(value: str) -> str:
    trimmed = value.strip()

    if not trimmed or len(trimmed) > MAX_EMAIL_LENGTH:
        raise ValueError("Invalid email.")

    try:
        trimmed.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("Invalid email.") from None

    try:
        validated = validate_email(
            trimmed,
            check_deliverability=False,
            allow_smtputf8=False,
            allow_quoted_local=False,
            allow_domain_literal=False,
            allow_display_name=False,
        )
    except EmailNotValidError:
        raise ValueError("Invalid email.") from None

    if validated.ascii_email is None:
        raise ValueError("Invalid email.")

    canonical = validated.ascii_email.lower()

    if len(canonical) > MAX_EMAIL_LENGTH:
        raise ValueError("Invalid email.")

    return canonical


def normalize_password(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Invalid password.") from None

    normalized = unicodedata.normalize("NFC", value)

    if not MIN_PASSWORD_LENGTH <= len(normalized) <= MAX_PASSWORD_LENGTH:
        raise ValueError("Invalid password.")

    return normalized

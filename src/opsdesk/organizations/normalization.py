MIN_ORGANIZATION_NAME_LENGTH = 1
MAX_ORGANIZATION_NAME_LENGTH = 255

_FORBIDDEN_NAME_CHARACTERS = frozenset(
    {
        "\x00",
        "\n",
        "\r",
        "\t",
    }
)


def normalize_organization_name(value: str) -> str:
    if any(character in value for character in _FORBIDDEN_NAME_CHARACTERS):
        raise ValueError("Invalid organization name.")

    normalized = value.strip()

    if not (
        MIN_ORGANIZATION_NAME_LENGTH <= len(normalized) <= MAX_ORGANIZATION_NAME_LENGTH
    ):
        raise ValueError("Invalid organization name.")

    return normalized

FORBIDDEN_TITLE_CHARACTERS = frozenset(
    {
        "\x00",
        "\t",
        "\n",
        "\r",
    }
)


def normalize_ticket_title(value: str) -> str:
    if any(character in value for character in FORBIDDEN_TITLE_CHARACTERS):
        raise ValueError("Invalid ticket title.")

    normalized = value.strip()

    if not 1 <= len(normalized) <= 255:
        raise ValueError("Invalid ticket title.")

    return normalized


def normalize_ticket_description(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Invalid ticket description.")

    normalized = value.strip()

    if not 1 <= len(normalized) <= 10_000:
        raise ValueError("Invalid ticket description.")

    return normalized

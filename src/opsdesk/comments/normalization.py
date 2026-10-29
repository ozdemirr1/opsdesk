def normalize_comment_content(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid comment content.")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if any(ord(c) < 32 and c not in "\n\t" for c in normalized):
        raise ValueError("Invalid comment content.")
    normalized = normalized.strip()
    if not 1 <= len(normalized) <= 10_000:
        raise ValueError("Invalid comment content.")
    return normalized

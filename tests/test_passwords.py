from opsdesk.identity.passwords import PasswordHasher


def test_hash_is_not_plain_text():
    hasher = PasswordHasher()
    plain_password = "my_secure_password_123"
    password_hash = hasher.hash_password(plain_password)

    assert password_hash != plain_password


def test_hash_starts_with_argon2id():
    hasher = PasswordHasher()
    password_hash = hasher.hash_password("my_secure_password_123")

    assert password_hash.startswith("$argon2id$")


def test_verify_correct_password():
    hasher = PasswordHasher()
    plain_password = "my_secure_password_123"
    password_hash = hasher.hash_password(plain_password)

    assert hasher.verify_password(plain_password, password_hash) is True


def test_verify_incorrect_password():
    hasher = PasswordHasher()
    plain_password = "my_secure_password_123"
    password_hash = hasher.hash_password(plain_password)

    assert hasher.verify_password("wrong_password_123", password_hash) is False


def test_same_password_generates_different_hashes_but_both_verify():
    hasher = PasswordHasher()
    plain_password = "my_secure_password_123"

    hash_one = hasher.hash_password(plain_password)
    hash_two = hasher.hash_password(plain_password)

    assert hash_one != hash_two
    assert hasher.verify_password(plain_password, hash_one) is True
    assert hasher.verify_password(plain_password, hash_two) is True

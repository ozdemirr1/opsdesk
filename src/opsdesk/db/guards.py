def validate_test_target(
    *,
    host: str,
    port: int,
    database: str,
) -> None:
    if host != "127.0.0.1" or port != 5432 or database != "opsdesk_product_test":
        raise ValueError("Unsafe integration-test database target.")

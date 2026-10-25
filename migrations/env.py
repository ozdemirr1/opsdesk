from logging.config import fileConfig

from alembic import context
from sqlalchemy.exc import SQLAlchemyError

from opsdesk.db.config import IntegrationDatabaseSettings
from opsdesk.db.connection import create_integration_engine
from opsdesk.db.development import (
    DevelopmentMigrationSettings,
    create_development_migration_engine,
    verify_development_connection,
)
from opsdesk.db.hosted import (
    HostedMigrationSettings,
    create_hosted_migration_engine,
    verify_hosted_connection,
)
from opsdesk.db.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """Exclude the test probe table from schema comparison."""
    return not (type_ == "table" and name == "integration_probe")


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Generate PostgreSQL SQL without opening a database connection."""
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Default to test; other targets require explicit selection."""
    target = context.get_x_argument(as_dictionary=True).get("target", "test")

    if target == "test":
        engine = create_integration_engine(IntegrationDatabaseSettings())
    elif target == "development":
        engine = create_development_migration_engine(DevelopmentMigrationSettings())
    elif target == "hosted":
        engine = create_hosted_migration_engine(HostedMigrationSettings())
    else:
        raise ValueError("Unknown migration target; use test, development or hosted.")

    try:
        with engine.connect() as connection:
            with connection.begin():
                if target == "development":
                    verify_development_connection(connection)
                elif target == "hosted":
                    verify_hosted_connection(connection)

                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    include_name=include_name,
                )

                with context.begin_transaction():
                    context.run_migrations()
    except SQLAlchemyError:
        raise RuntimeError("Migration database operation failed.") from None
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

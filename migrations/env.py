import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

from app.extensions import db
from app import models


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
target_metadata = db.metadata
AUTOGENERATE_PLUGINS = (
    "alembic.autogenerate.*",
    "alembic.ext.checkconstraint_byname",
)


def run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        autogenerate_plugins=AUTOGENERATE_PLUGINS,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline():
    context.configure(
        url=os.environ["DATABASE_URL"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        autogenerate_plugins=AUTOGENERATE_PLUGINS,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connection = config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
        return

    engine = create_engine(os.environ["DATABASE_URL"], poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            run_migrations(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

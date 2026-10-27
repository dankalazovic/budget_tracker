from pathlib import Path

import click
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from flask.cli import with_appcontext
from sqlalchemy import inspect

from app.extensions import db


def migration_config(connection=None):
    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


@click.command("init-db")
@with_appcontext
def init_db():
    """Apply migrations to an empty or already versioned database."""
    with db.engine.begin() as connection:
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        revision = MigrationContext.configure(connection).get_current_revision()
        if tables and revision is None:
            raise click.ClickException(
                "Existing database has no Alembic revision. Verify its schema "
                "before marking the initial revision; no existing data was changed."
            )
        command.upgrade(migration_config(connection), "head")

    click.echo("Database migrations applied. Existing data was preserved.")


def register_commands(app):
    app.cli.add_command(init_db)

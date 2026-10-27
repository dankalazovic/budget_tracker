import click
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex

from app import app, db
from app.models import Category


@app.cli.command("init-db")
def init_db():
    """Create missing tables and add the category name index without deleting data."""
    try:
        with db.engine.begin() as connection:
            db.metadata.create_all(bind=connection)

            # create_all ne dodaje indekse tabelama koje vec postoje.
            for index in Category.__table__.indexes:
                connection.execute(CreateIndex(index, if_not_exists=True))
    except IntegrityError:
        raise click.ClickException(
            "Database initialization failed. Check for duplicate category names "
            "(case-insensitive). No existing data was deleted."
        ) from None

    click.echo("Database initialized. Existing data was preserved.")

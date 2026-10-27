import atexit
import os
from pathlib import Path
import unittest
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
source_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not source_url:
    raise RuntimeError("Set TEST_DATABASE_URL or DATABASE_URL before running tests")
source_url = make_url(source_url)
if source_url.get_backend_name() != "postgresql":
    raise RuntimeError("Integration tests require PostgreSQL")

# Jedna zasebna, nasumicno imenovana sema postoji samo tokom ovog test procesa.
TEST_SCHEMA = "tracker_test_" + uuid4().hex
admin_engine = create_engine(source_url, poolclass=NullPool)
with admin_engine.begin() as connection:
    connection.execute(CreateSchema(TEST_SCHEMA))

test_url = source_url.update_query_dict({"options": "-csearch_path=" + TEST_SCHEMA})
os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)


def cleanup_test_schema():
    if "app" in globals():
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
    # Nikada ne uklanjamo semu iz korisnicke konfiguracije, samo nas UUID naziv.
    assert TEST_SCHEMA.startswith("tracker_test_") and len(TEST_SCHEMA) == 45
    try:
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(TEST_SCHEMA, cascade=True))
    finally:
        admin_engine.dispose()


atexit.register(cleanup_test_schema)

from app import app, db


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.app_context = app.app_context()
        self.app_context.push()
        self.assertEqual(db.engine.dialect.name, "postgresql")
        with db.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT current_schema()").scalar_one(), TEST_SCHEMA)
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

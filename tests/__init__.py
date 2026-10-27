import os
import unittest

# Testovi koriste samo privremenu bazu u memoriji.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import app, db


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.app_context = app.app_context()
        self.app_context.push()
        self.assertEqual(db.engine.dialect.name, "sqlite")
        self.assertEqual(db.engine.url.database, ":memory:")
        with db.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

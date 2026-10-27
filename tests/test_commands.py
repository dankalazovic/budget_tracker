from datetime import date
from decimal import Decimal

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app import app, db
from app.commands import migration_config
from app.models import Category, Transaction
from tests import BaseTestCase


class InitDatabaseTests(BaseTestCase):
    def tearDown(self):
        db.session.remove()
        # Alembic tabela nije deo modela, pa je db.drop_all ne uklanja.
        with db.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        super().tearDown()

    def start_with_empty_database(self):
        db.session.remove()
        db.drop_all()

    def test_creates_tables_and_records_migration_revision(self):
        self.start_with_empty_database()

        result = app.test_cli_runner().invoke(args=["init-db"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            set(inspect(db.engine).get_table_names()),
            {"category", "transactions", "alembic_version"},
        )
        expected_revision = ScriptDirectory.from_config(migration_config()).get_current_head()
        self.assertIsNotNone(expected_revision)
        with db.engine.connect() as connection:
            revision = MigrationContext.configure(connection).get_current_revision()
        self.assertEqual(revision, expected_revision)

    def test_repeated_upgrade_preserves_existing_rows_and_ids(self):
        self.start_with_empty_database()
        runner = app.test_cli_runner()
        initial = runner.invoke(args=["init-db"])
        self.assertEqual(initial.exit_code, 0, initial.output)

        category = Category(id=17, name="Hrana", color="#123456")
        db.session.add(category)
        db.session.commit()
        transaction = Transaction(
            id=29,
            type="expense",
            amount=Decimal("12.50"),
            date=date(2026, 10, 27),
            description="Rucak",
            category_id=category.id,
        )
        db.session.add(transaction)
        db.session.commit()
        original_transaction = transaction.to_dict()
        db.session.remove()

        for _ in range(2):
            result = runner.invoke(args=["init-db"])
            self.assertEqual(result.exit_code, 0, result.output)

        saved_category = db.session.get(Category, 17)
        self.assertEqual((saved_category.name, saved_category.color), ("Hrana", "#123456"))
        saved_transaction = db.session.get(Transaction, 29)
        self.assertEqual(saved_transaction.to_dict(), original_transaction)
        self.assertEqual(len(db.session.execute(db.select(Category)).scalars().all()), 1)
        self.assertEqual(len(db.session.execute(db.select(Transaction)).scalars().all()), 1)

    def test_unversioned_database_with_data_is_rejected_without_changes(self):
        category = Category(id=17, name="Hrana", color="#123456")
        db.session.add(category)
        db.session.commit()
        original = db.session.execute(
            db.select(Category.id, Category.name, Category.color)
        ).all()
        db.session.remove()
        tables_before = set(inspect(db.engine).get_table_names())

        result = app.test_cli_runner().invoke(args=["init-db"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("no Alembic revision", result.output)
        self.assertEqual(set(inspect(db.engine).get_table_names()), tables_before)
        saved = db.session.execute(
            db.select(Category.id, Category.name, Category.color)
        ).all()
        self.assertEqual(saved, original)

    def test_unversioned_database_with_empty_tables_is_also_rejected(self):
        tables_before = set(inspect(db.engine).get_table_names())

        result = app.test_cli_runner().invoke(args=["init-db"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("no Alembic revision", result.output)
        self.assertEqual(set(inspect(db.engine).get_table_names()), tables_before)
        self.assertEqual(db.session.execute(db.select(Category)).scalars().all(), [])
        self.assertEqual(db.session.execute(db.select(Transaction)).scalars().all(), [])

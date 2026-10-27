from datetime import date
from decimal import Decimal

from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app import app, db
from app.commands import migration_config
from app.models import Category, Transaction
from app.schemas import TransactionResponse
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
        self.assertEqual(inspect(db.engine).get_check_constraints("transactions"), [])
        self.assertEqual(len(inspect(db.engine).get_foreign_keys("transactions")), 1)

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
        original_transaction = TransactionResponse.model_validate(transaction).model_dump(mode="json")
        db.session.remove()

        for _ in range(2):
            result = runner.invoke(args=["init-db"])
            self.assertEqual(result.exit_code, 0, result.output)

        saved_category = db.session.get(Category, 17)
        self.assertEqual((saved_category.name, saved_category.color), ("Hrana", "#123456"))
        saved_transaction = db.session.get(Transaction, 29)
        saved_data = TransactionResponse.model_validate(saved_transaction).model_dump(mode="json")
        self.assertEqual(saved_data, original_transaction)
        self.assertEqual(len(db.session.execute(db.select(Category)).scalars().all()), 1)
        self.assertEqual(len(db.session.execute(db.select(Transaction)).scalars().all()), 1)

    def test_removing_checks_preserves_existing_data_and_foreign_key(self):
        self.start_with_empty_database()
        with db.engine.begin() as connection:
            command.upgrade(migration_config(connection), "a128effd0953")

        initial_checks = inspect(db.engine).get_check_constraints("transactions")
        self.assertEqual(
            {constraint["name"] for constraint in initial_checks},
            {"ck_transaction_type", "ck_transaction_amount"},
        )
        category = Category(id=17, name="Hrana", color="#123456")
        transaction = Transaction(
            id=29,
            type="expense",
            amount=Decimal("12.50"),
            date=date(2026, 10, 27),
            description="Rucak",
            category=category,
        )
        db.session.add(transaction)
        db.session.commit()
        original = TransactionResponse.model_validate(transaction).model_dump(mode="json")
        db.session.remove()

        result = app.test_cli_runner().invoke(args=["init-db"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(inspect(db.engine).get_check_constraints("transactions"), [])
        foreign_keys = inspect(db.engine).get_foreign_keys("transactions")
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(foreign_keys[0]["referred_table"], "category")
        self.assertEqual(foreign_keys[0]["constrained_columns"], ["category_id"])
        saved = db.session.get(Transaction, 29)
        self.assertEqual(
            TransactionResponse.model_validate(saved).model_dump(mode="json"), original
        )
        self.assertEqual(db.session.get(Category, 17).name, "Hrana")

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

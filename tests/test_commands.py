from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.models import Category
from tests import BaseTestCase


class InitDatabaseTests(BaseTestCase):
    def test_creates_missing_tables(self):
        db.session.remove()
        db.drop_all()

        result = app.test_cli_runner().invoke(args=["init-db"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(inspect(db.engine).has_table("category"))

    def test_can_run_twice_without_changing_existing_data(self):
        category = Category(name="Hrana", color="#123456")
        db.session.add(category)
        db.session.commit()
        category_id = category.id
        db.session.remove()

        runner = app.test_cli_runner()
        first = runner.invoke(args=["init-db"])
        second = runner.invoke(args=["init-db"])

        self.assertEqual(first.exit_code, 0, first.output)
        self.assertEqual(second.exit_code, 0, second.output)
        self.assertEqual(len(db.session.execute(db.select(Category)).scalars().all()), 1)
        saved = db.session.get(Category, category_id)
        self.assertEqual(saved.name, "Hrana")
        self.assertEqual(saved.color, "#123456")

    def test_adds_index_to_existing_table_without_deleting_data(self):
        category = Category(name="Hrana", color="#123456")
        db.session.add(category)
        db.session.commit()
        category_id = category.id
        db.session.remove()

        # Ovako predstavljamo staru tabelu, koja jos nema novi indeks.
        for index in Category.__table__.indexes:
            index.drop(bind=db.engine)

        result = app.test_cli_runner().invoke(args=["init-db"])

        self.assertEqual(result.exit_code, 0, result.output)
        saved = db.session.get(Category, category_id)
        self.assertEqual(saved.name, "Hrana")
        self.assertEqual(saved.color, "#123456")

        # Proveravamo ponasanje baze, a ne samo prisustvo imena indeksa.
        response = self.client.post(
            "/categories", json={"name": "hrana", "color": "#FFFFFF"}
        )
        self.assertEqual(response.status_code, 409)

        db.session.add(Category(name="HRANA", color="#FFFFFF"))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_existing_duplicates_are_reported_and_preserved(self):
        db.session.remove()
        for index in Category.__table__.indexes:
            index.drop(bind=db.engine)

        db.session.add_all([
            Category(name="Hrana", color="#123456"),
            Category(name="hrana", color="#FFFFFF"),
        ])
        db.session.commit()
        original = db.session.execute(
            db.select(Category.id, Category.name, Category.color).order_by(Category.id)
        ).all()
        db.session.remove()

        result = app.test_cli_runner().invoke(args=["init-db"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("duplicate category names", result.output)
        saved = db.session.execute(
            db.select(Category.id, Category.name, Category.color).order_by(Category.id)
        ).all()
        self.assertEqual(saved, original)

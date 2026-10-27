import unittest

from app import app, create_app, db


class AppStructureTests(unittest.TestCase):
    def test_factory_creates_independent_app_with_all_routes(self):
        application = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.assertIsNot(application, app)

        with app.app_context():
            original_engine = db.engine
        with application.app_context():
            self.assertEqual(db.engine.url.database, ":memory:")
            self.assertIsNot(db.engine, original_engine)
            db.engine.dispose()

        routes = {}
        for rule in application.url_map.iter_rules():
            routes.setdefault(rule.rule, set()).update(rule.methods)
        expected = {
            "/": {"GET"},
            "/categories": {"GET", "POST"},
            "/categories/<int:category_id>": {"PUT", "DELETE"},
            "/transactions": {"GET", "POST"},
            "/transactions/<int:transaction_id>": {"GET", "PUT", "DELETE"},
            "/budgets": {"GET"},
            "/budgets/<month>/<int:category_id>": {"PUT", "DELETE"},
            "/summary": {"GET"},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertTrue(methods.issubset(routes.get(path, set())))

        response = application.test_client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"message": "Budget Tracker API is running"})

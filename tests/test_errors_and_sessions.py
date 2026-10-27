from loguru import logger
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import BadRequest

from app import app, create_app, db
from app.models import Category
from tests import BaseTestCase


class ErrorAndSessionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.application = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
        })
        self.request_sessions = []

        @self.application.get("/test/session")
        def session_marker():
            self.request_sessions.append(db.session())
            return {"ok": True}

        @self.application.post("/test/handled-error")
        def handled_error():
            db.session.add(Category(name="Not committed", color="#123456"))
            db.session.flush()
            raise BadRequest("Request rejected")

        @self.application.post("/test/unhandled-error")
        def unhandled_error():
            db.session.add(Category(name="Private input value", color="#123456"))
            db.session.flush()
            raise RuntimeError("private_exception_details")

        @self.application.get("/test/database-error")
        def database_error():
            raise OperationalError(
                "SELECT secret_column", {"password": "private_password"},
                RuntimeError("private_database_details"),
            )

        @self.application.post("/test/unknown-constraint")
        def unknown_constraint():
            db.session.add(Category(name=None, color="#123456"))
            db.session.flush()
            return {"ok": True}

        # Isti app context ostaje aktivan, da teardown_request mora da ukloni sesiju.
        self.request_context = self.application.app_context()
        self.request_context.push()
        self.client = self.application.test_client()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.request_context.pop()
        super().tearDown()

    def assert_no_categories(self):
        count = db.session.scalar(db.select(db.func.count()).select_from(Category))
        self.assertEqual(count, 0)

    def test_http_errors_are_json_and_method_not_allowed_keeps_allow_header(self):
        missing = self.client.get("/not-a-route")
        self.assertEqual(missing.status_code, 404)
        self.assertIsInstance(missing.get_json()["error"], str)

        invalid_method = self.client.patch("/categories", json={})
        self.assertEqual(invalid_method.status_code, 405)
        self.assertIsInstance(invalid_method.get_json()["error"], str)
        allowed = {method.strip() for method in invalid_method.headers["Allow"].split(",")}
        self.assertTrue({"GET", "POST"}.issubset(allowed))

        invalid_json = self.client.post(
            "/categories", data="{", content_type="application/json"
        )
        self.assertEqual(invalid_json.status_code, 400)
        self.assertEqual(invalid_json.get_json(), {"error": "Invalid JSON data"})

    def test_each_request_uses_a_new_session(self):
        self.assertEqual(self.client.get("/test/session").status_code, 200)
        self.assertEqual(self.client.get("/test/session").status_code, 200)

        self.assertEqual(len(self.request_sessions), 2)
        self.assertIsNot(self.request_sessions[0], self.request_sessions[1])

    def test_handled_error_rolls_back_flushed_changes(self):
        response = self.client.post("/test/handled-error")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Request rejected"})
        self.assert_no_categories()
        self.assertEqual(self.client.get("/test/session").status_code, 200)

    def test_unhandled_error_rolls_back_and_hides_exception_details(self):
        response = self.client.post("/test/unhandled-error")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error"})
        self.assert_no_categories()
        created = self.client.post(
            "/categories", json={"name": "Hrana", "color": "#123456"}
        )
        self.assertEqual(created.status_code, 201)

    def test_successful_commit_survives_request_cleanup(self):
        created = self.client.post(
            "/categories", json={"name": "Hrana", "color": "#123456"}
        )
        self.assertEqual(created.status_code, 201)

        listed = self.client.get("/categories")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json(), [created.get_json()])

    def test_sqlalchemy_error_returns_generic_json_and_next_request_works(self):
        response = self.client.get("/test/database-error")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error"})
        self.assertNotIn("private_password", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/test/session").status_code, 200)

    def test_unknown_constraint_is_not_reported_as_duplicate_category(self):
        response = self.client.post("/test/unknown-constraint")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error"})
        self.assert_no_categories()
        created = self.client.post(
            "/categories", json={"name": "Hrana", "color": "#123456"}
        )
        self.assertEqual(created.status_code, 201)

    def test_logs_record_requests_and_error_class_without_private_values(self):
        messages = []
        sink = logger.add(
            messages.append, format="{level}|{message}",
            level="DEBUG", backtrace=False, diagnose=False,
        )
        try:
            self.client.get("/test/session?token=private_query_value")
            self.client.get("/test/database-error")
            self.client.post(
                "/test/unhandled-error", json={"password": "private_body_value"}
            )
        finally:
            logger.remove(sink)

        text = "\n".join(str(message) for message in messages)
        self.assertTrue(any(message.record["level"].name == "INFO" for message in messages))
        self.assertTrue(any(message.record["level"].name == "ERROR" for message in messages))
        self.assertIn("OperationalError", text)
        for private_value in (
            "private_query_value", "private_body_value", "private_password",
            "private_database_details", "private_exception_details", "SELECT secret_column",
        ):
            with self.subTest(private_value=private_value):
                self.assertNotIn(private_value, text)

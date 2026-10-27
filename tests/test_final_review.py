from io import BytesIO

from tests import BaseTestCase, TEST_SCHEMA
from app import app, create_app, db


class PersistenceTests(BaseTestCase):
    def test_saved_data_survives_new_app_engine_and_connection_pool(self):
        category_response = self.client.post(
            "/categories", json={"name": "Hrana", "color": "#123456"}
        )
        self.assertEqual(category_response.status_code, 201)
        category = category_response.get_json()
        transaction_response = self.client.post("/transactions", json={
            "type": "income", "amount": "100.00", "date": "2026-10-01",
            "category_id": category["id"], "description": "Prihod",
        })
        self.assertEqual(transaction_response.status_code, 201)
        transaction = transaction_response.get_json()
        budget_response = self.client.put(
            f"/budgets/2026-10/{category['id']}", json={"amount": "20.00"}
        )
        self.assertEqual(budget_response.status_code, 201)
        budget = budget_response.get_json()
        upload = self.client.post("/transactions/import", data={
            "file": (BytesIO(
                b"type,amount,date,description,category\n"
                b"expense,12.50,2026-10-02,Rucak,hrana\n"
            ), "transactions.csv"),
        }, content_type="multipart/form-data", buffered=True)
        try:
            self.assertEqual(upload.status_code, 200, upload.get_json())
            self.assertEqual(upload.get_json(), {"imported": 1, "failed": 0, "errors": []})
        finally:
            upload.close()
        original_list = self.client.get("/transactions").get_json()
        original_summary = self.client.get("/summary?month=2026-10").get_json()
        self.assertEqual(original_summary["balance"], "87.50")
        self.assertEqual(original_summary["categories"][0]["remaining"], "7.50")
        original_engine = db.engine
        db.session.remove()
        original_engine.dispose()

        # Nova aplikacija dobija nov engine/pool, ali istu izolovanu PostgreSQL bazu.
        restarted = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
            "LOG_LEVEL": "ERROR",
        })
        with restarted.app_context():
            try:
                self.assertIsNot(db.engine, original_engine)
                with db.engine.connect() as connection:
                    self.assertEqual(
                        connection.exec_driver_sql("SELECT current_schema()").scalar_one(),
                        TEST_SCHEMA,
                    )
                client = restarted.test_client()
                self.assertEqual(client.get("/categories").get_json(), [category])
                self.assertEqual(
                    client.get(f"/transactions/{transaction['id']}").get_json(), transaction
                )
                self.assertEqual(client.get("/transactions").get_json(), original_list)
                self.assertEqual(client.get("/budgets?month=2026-10").get_json(), [budget])
                self.assertEqual(
                    client.get("/summary?month=2026-10").get_json(), original_summary
                )
            finally:
                db.session.remove()
                db.engine.dispose()

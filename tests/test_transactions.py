import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from tests import BaseTestCase
from app import db
from app.models import Category, Transaction


class TransactionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        response = self.client.post(
            "/categories", json={"name": "Hrana", "color": "#123456"}
        )
        self.assertEqual(response.status_code, 201)
        self.category = response.get_json()

    def valid_data(self, **changes):
        data = {
            "type": "expense",
            "amount": "12.50",
            "date": "2026-10-27",
            "description": "Rucak",
            "category_id": self.category["id"],
        }
        data.update(changes)
        return data

    def create_transaction(self, **changes):
        response = self.client.post("/transactions", json=self.valid_data(**changes))
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def assert_invalid_field(self, field, values):
        original = self.create_transaction()
        url = f"/transactions/{original['id']}"

        for method, target in (("POST", "/transactions"), ("PUT", url)):
            for value in values:
                with self.subTest(method=method, field=field, value=value):
                    response = self.client.open(
                        target, method=method, json=self.valid_data(**{field: value})
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())
                    self.assertEqual(self.client.get(url).get_json(), original)

        transactions = db.session.execute(db.select(Transaction)).scalars().all()
        self.assertEqual(len(transactions), 1)

    def test_create_transaction_stores_values_and_links_category(self):
        created = self.create_transaction()

        self.assertIsInstance(created["id"], int)
        expected = self.valid_data()
        expected["id"] = created["id"]
        self.assertEqual(created, expected)

        stored = db.session.get(Transaction, created["id"])
        category = db.session.get(Category, self.category["id"])
        self.assertEqual(stored.amount, Decimal("12.50"))
        self.assertEqual(stored.date, date(2026, 10, 27))
        self.assertEqual(stored.category, category)
        self.assertIn(stored, category.transactions)

    def test_create_accepts_income_and_numeric_amounts(self):
        for amount, expected in ((12, "12.00"), (12.5, "12.50"), (0.01, "0.01")):
            with self.subTest(amount=amount):
                created = self.create_transaction(type="income", amount=amount)
                self.assertEqual(created["type"], "income")
                self.assertEqual(created["amount"], expected)

    def test_create_accepts_minimum_and_maximum_amount(self):
        for amount in ("0.01", "1000000.00"):
            with self.subTest(amount=amount):
                created = self.create_transaction(amount=amount)
                self.assertEqual(created["amount"], amount)

    def test_create_requires_type_amount_date_and_category(self):
        for field in ("type", "amount", "date", "category_id"):
            with self.subTest(missing=field):
                data = self.valid_data()
                del data[field]
                response = self.client.post("/transactions", json=data)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

        self.assertEqual(db.session.execute(db.select(Transaction)).scalars().all(), [])

    def test_description_is_optional_and_empty_means_no_description(self):
        data = self.valid_data()
        del data["description"]
        response = self.client.post("/transactions", json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.get_json()["description"])

        for description in (None, ""):
            with self.subTest(description=description):
                created = self.create_transaction(description=description)
                self.assertIsNone(created["description"])

    def test_description_preserves_spaces_and_accepts_200_characters(self):
        for description in ("  Rucak  ", " ", "A" * 200):
            with self.subTest(description=description):
                created = self.create_transaction(description=description)
                self.assertEqual(created["description"], description)

    def test_create_and_update_reject_invalid_types(self):
        self.assert_invalid_field(
            "type", (None, True, 1, "", "Income", "EXPENSE", "other", [], {})
        )

    def test_create_and_update_reject_invalid_amounts(self):
        self.assert_invalid_field("amount", (
            None, True, False, "", "abc", "NaN", "sNaN", "Infinity", "-Infinity",
            [], {}, 0, -1, "0.00", "-0.01", "1000000.01", "12.345",
            "12.500", "1_0", " 12.50 ",
        ))

    def test_raw_json_amount_keeps_precision_and_rejects_nonfinite_values(self):
        original = self.create_transaction()
        url = f"/transactions/{original['id']}"
        invalid_numbers = (
            "1.00000000000000001", "NaN", "Infinity", "-Infinity",
            "1e999999999", "1e-999999999",
        )

        for method, target in (("POST", "/transactions"), ("PUT", url)):
            for number in invalid_numbers:
                with self.subTest(method=method, number=number):
                    # Broj ostaje u izvornom JSON obliku, bez Python float konverzije.
                    body = json.dumps(self.valid_data()).replace('"12.50"', number)
                    response = self.client.open(
                        target, method=method, data=body,
                        content_type="application/json"
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())
                    self.assertEqual(self.client.get(url).get_json(), original)

    def test_create_and_update_reject_invalid_dates(self):
        self.assert_invalid_field("date", (
            None, True, 20261027, "", "2026-02-29", "2026-13-01",
            "2026-04-31", "0000-01-01", "20261027", "2026-W44-2",
            "2026-1-01", "2026-10-27T12:00:00", [], {},
        ))

    def test_valid_leap_day_is_accepted(self):
        created = self.create_transaction(date="2024-02-29")
        self.assertEqual(created["date"], "2024-02-29")

    def test_create_and_update_reject_invalid_category_ids(self):
        self.assert_invalid_field("category_id", (
            None, True, False, 0, -1, "1", 1.0, 999,
            2147483648, 2 ** 63, 10 ** 100, [], {},
        ))

    def test_create_and_update_reject_invalid_descriptions(self):
        self.assert_invalid_field("description", (
            True, 123, [], {}, "A" * 201,
            "Rucak\x00", "Rucak\ud800", "Rucak\udfff",
        ))

    def test_create_and_update_reject_invalid_json(self):
        original = self.create_transaction()
        url = f"/transactions/{original['id']}"

        for method, target in (("POST", "/transactions"), ("PUT", url)):
            for body in ("null", "[]", '"tekst"', "123", "true", "{", ""):
                with self.subTest(method=method, body=body):
                    response = self.client.open(
                        target, method=method, data=body,
                        content_type="application/json"
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())

            with self.subTest(method=method, content_type="text/plain"):
                response = self.client.open(
                    target, method=method, data=json.dumps(self.valid_data()),
                    content_type="text/plain"
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.client.get(url).get_json(), original)

    def test_get_transaction_returns_saved_data(self):
        created = self.create_transaction()

        response = self.client.get(f"/transactions/{created['id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), created)

    def test_update_can_change_every_field_and_category(self):
        original = self.create_transaction()
        response = self.client.post(
            "/categories", json={"name": "Plata", "color": "#FFFFFF"}
        )
        new_category = response.get_json()
        changes = {
            "type": "income", "amount": "300.01", "date": "2026-11-01",
            "description": "Dodatni posao", "category_id": new_category["id"],
        }

        response = self.client.put(f"/transactions/{original['id']}", json=changes)

        self.assertEqual(response.status_code, 200)
        expected = dict(changes, id=original["id"])
        self.assertEqual(response.get_json(), expected)
        stored = db.session.get(Transaction, original["id"])
        self.assertEqual(stored.category_id, new_category["id"])
        self.assertEqual(stored.amount, Decimal("300.01"))

    def test_partial_update_and_empty_object_keep_omitted_fields(self):
        original = self.create_transaction()
        url = f"/transactions/{original['id']}"

        response = self.client.put(url, json={"amount": "20.00"})
        self.assertEqual(response.status_code, 200)
        expected = dict(original, amount="20.00")
        self.assertEqual(response.get_json(), expected)

        response = self.client.put(url, json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)

        response = self.client.put(url, json={"description": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["description"])

    def test_missing_or_out_of_range_transaction_returns_404(self):
        for transaction_id in (0, 999, 2147483648, 2 ** 63, 10 ** 100):
            for method in ("GET", "PUT", "DELETE"):
                with self.subTest(transaction_id=transaction_id, method=method):
                    response = self.client.open(
                        f"/transactions/{transaction_id}", method=method,
                        json=self.valid_data()
                    )
                    self.assertEqual(response.status_code, 404)
                    self.assertIn("error", response.get_json())

    def test_delete_removes_only_requested_transaction(self):
        first = self.create_transaction()
        second = self.create_transaction(amount="15.00")

        response = self.client.delete(f"/transactions/{first['id']}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.client.get(f"/transactions/{first['id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/transactions/{second['id']}").get_json(), second)
        self.assertIsNotNone(db.session.get(Category, self.category["id"]))

    def test_category_with_transaction_cannot_be_deleted(self):
        created = self.create_transaction()
        category = db.session.get(Category, self.category["id"])
        self.assertEqual(len(category.transactions), 1)

        response = self.client.delete(f"/categories/{self.category['id']}")

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.get_json())
        self.assertIsNotNone(db.session.get(Category, self.category["id"]))
        self.assertEqual(self.client.get(f"/transactions/{created['id']}").get_json(), created)

        self.assertEqual(
            self.client.delete(f"/transactions/{created['id']}").status_code, 204
        )
        self.assertEqual(
            self.client.delete(f"/categories/{self.category['id']}").status_code, 204
        )

    def test_database_rejects_invalid_type_amount_and_missing_category(self):
        invalid_values = (
            {"type": "other"}, {"amount": Decimal("0")},
            {"amount": Decimal("-0.01")}, {"amount": Decimal("1000000.01")},
            {"category_id": 999},
        )
        for changes in invalid_values:
            with self.subTest(changes=changes):
                data = {
                    "type": "expense", "amount": Decimal("12.50"),
                    "date": date(2026, 10, 27), "category_id": self.category["id"],
                }
                data.update(changes)
                db.session.add(Transaction(**data))

                with self.assertRaises(IntegrityError):
                    db.session.commit()

                db.session.rollback()

        self.assertEqual(db.session.execute(db.select(Transaction)).scalars().all(), [])

    def test_database_prevents_deleting_category_with_loaded_transactions(self):
        created = self.create_transaction()
        category = db.session.get(Category, self.category["id"])
        self.assertEqual(len(category.transactions), 1)
        db.session.delete(category)

        with self.assertRaises(IntegrityError):
            db.session.commit()

        db.session.rollback()
        self.assertIsNotNone(db.session.get(Category, self.category["id"]))
        self.assertIsNotNone(db.session.get(Transaction, created["id"]))

    def test_create_handles_category_disappearing_after_validation(self):
        real_get = db.session.get
        category = real_get(Category, self.category["id"])

        def get_before_category_disappeared(model, record_id, *args, **kwargs):
            if model is Category and record_id == 999:
                return category
            return real_get(model, record_id, *args, **kwargs)

        # Provera vidi kategoriju, ali stvarni FK odbija nepostojeci ID pri upisu.
        with patch.object(db.session, "get", side_effect=get_before_category_disappeared):
            response = self.client.post(
                "/transactions", json=self.valid_data(category_id=999)
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Category not found"})
        self.assertEqual(db.session.execute(db.select(Transaction)).scalars().all(), [])

        self.create_transaction()
        self.assertEqual(len(db.session.execute(db.select(Transaction)).scalars().all()), 1)

    def test_update_handles_category_disappearing_and_preserves_original(self):
        original = self.create_transaction()
        url = f"/transactions/{original['id']}"
        real_get = db.session.get
        category = real_get(Category, self.category["id"])

        def get_before_category_disappeared(model, record_id, *args, **kwargs):
            if model is Category and record_id == 999:
                return category
            return real_get(model, record_id, *args, **kwargs)

        with patch.object(db.session, "get", side_effect=get_before_category_disappeared):
            response = self.client.put(
                url, json={"category_id": 999, "amount": "20.00"}
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Category not found"})
        self.assertEqual(self.client.get(url).get_json(), original)

        self.create_transaction()
        self.assertEqual(len(db.session.execute(db.select(Transaction)).scalars().all()), 2)

    def test_delete_category_handles_transaction_added_after_precheck(self):
        original = self.create_transaction()

        # Pocetna provera ne vidi transakciju, ali baza i dalje stiti kategoriju.
        with patch.object(db.session, "execute") as execute:
            execute.return_value.scalar_one_or_none.return_value = None
            response = self.client.delete(f"/categories/{self.category['id']}")
            execute.assert_called_once()

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.get_json())
        self.assertIsNotNone(db.session.get(Category, self.category["id"]))
        self.assertEqual(
            self.client.get(f"/transactions/{original['id']}").get_json(), original
        )

        self.create_transaction()
        self.assertEqual(len(db.session.execute(db.select(Transaction)).scalars().all()), 2)

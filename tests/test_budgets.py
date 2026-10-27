from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from sqlalchemy.exc import IntegrityError

from tests import BaseTestCase
from app import db
from app.models import Budget, Category


class BudgetTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.food = self.create_category("Hrana")

    def create_category(self, name):
        response = self.client.post(
            "/categories", json={"name": name, "color": "#123456"}
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def set_budget(self, month="2026-10", category_id=None, amount="200.00", status=201):
        if category_id is None:
            category_id = self.food["id"]
        response = self.client.put(
            f"/budgets/{month}/{category_id}", json={"amount": amount}
        )
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def list_budgets(self, month="2026-10"):
        response = self.client.get("/budgets", query_string={"month": month})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_put_creates_budget_and_links_existing_category(self):
        created = self.set_budget()

        self.assertEqual(created, {
            "id": created["id"], "month": "2026-10",
            "category_id": self.food["id"], "amount": "200.00",
        })
        self.assertIsInstance(created["id"], int)
        stored = db.session.get(Budget, created["id"])
        self.assertEqual(stored.month, date(2026, 10, 1))
        self.assertEqual(stored.amount, Decimal("200.00"))
        self.assertEqual(stored.category.id, self.food["id"])

    def test_repeated_put_updates_same_budget_instead_of_adding_another(self):
        original = self.set_budget()

        unchanged = self.set_budget(status=200)
        changed = self.set_budget(amount="250.50", status=200)

        self.assertEqual(unchanged, original)
        self.assertEqual(changed, dict(original, amount="250.50"))
        self.assertEqual(self.list_budgets(), [changed])
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(Budget)), 1)

    def test_same_category_in_other_month_and_other_category_are_allowed(self):
        other = self.create_category("Prevoz")
        october = self.set_budget()
        november = self.set_budget(month="2026-11", amount="300.00")
        other_category = self.set_budget(category_id=other["id"], amount="50.00")

        self.assertEqual(self.list_budgets(), [october, other_category])
        self.assertEqual(self.list_budgets("2026-11"), [november])

    def test_get_returns_only_requested_month_sorted_by_category_name(self):
        transport = self.create_category("Prevoz")
        leisure = self.create_category("Zabava")
        last = self.set_budget(category_id=leisure["id"])
        middle = self.set_budget(category_id=transport["id"])
        first = self.set_budget()
        self.set_budget(month="2026-11")

        self.assertEqual(self.list_budgets(), [first, middle, last])

    def test_get_returns_empty_list_for_month_without_budgets(self):
        self.assertEqual(self.list_budgets(), [])
        self.set_budget()
        self.assertEqual(self.list_budgets("2026-11"), [])

    def test_get_requires_one_valid_month_parameter(self):
        for query in ({}, {"month": ""}, {"month": "2026-13"}):
            with self.subTest(query=query):
                response = self.client.get("/budgets", query_string=query)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

        duplicate = self.client.get(
            "/budgets", query_string=[("month", "2026-10"), ("month", "2026-11")]
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("error", duplicate.get_json())

    def test_month_format_and_calendar_values_are_validated_for_all_operations(self):
        invalid_months = (
            "0000-01", "2026-00", "2026-13", "2026-1", "202610",
            "2026-10-01", "2026-W44", "abcd-ef", "2026-10 ",
        )
        for month in invalid_months:
            for method in ("PUT", "DELETE"):
                with self.subTest(month=month, method=method):
                    response = self.client.open(
                        f"/budgets/{month}/{self.food['id']}", method=method,
                        json={"amount": "200.00"},
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())
            with self.subTest(month=month, method="GET"):
                response = self.client.get("/budgets", query_string={"month": month})
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

        self.assertEqual(self.list_budgets(), [])

    def test_month_serialization_preserves_four_digit_early_year(self):
        created = self.set_budget(month="0001-01")
        self.assertEqual(created["month"], "0001-01")
        self.assertEqual(self.list_budgets("0001-01"), [created])

    def test_amount_accepts_boundaries_and_json_numbers(self):
        cases = (("0.01", "0.01"), ("1000000.00", "1000000.00"), (12, "12.00"), (12.5, "12.50"))
        for index, (amount, expected) in enumerate(cases):
            with self.subTest(amount=amount):
                created = self.set_budget(amount=amount, status=201 if index == 0 else 200)
                self.assertEqual(created["amount"], expected)

    def test_invalid_amount_does_not_change_existing_budget(self):
        original = self.set_budget()
        invalid_amounts = (
            None, True, False, "", "abc", [], {}, 0, -1, "0.00", "-0.01",
            "1000000.01", "12.345", "12.500", "NaN", "Infinity", "-Infinity",
            "1_0", " 12.50 ",
        )
        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                response = self.client.put(
                    f"/budgets/2026-10/{self.food['id']}", json={"amount": amount}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())
                self.assertEqual(self.list_budgets(), [original])

    def test_raw_json_amount_keeps_precision_and_rejects_nonfinite_numbers(self):
        original = self.set_budget()
        for amount in ("1.00000000000000001", "NaN", "Infinity", "-Infinity", "1e999999999", "1e-999999999"):
            with self.subTest(amount=amount):
                response = self.client.put(
                    f"/budgets/2026-10/{self.food['id']}",
                    data='{"amount":' + amount + '}', content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.list_budgets(), [original])

    def test_put_requires_amount_and_valid_json_object(self):
        for body in ("{}", "null", "[]", '"text"', "123", "true", "{", ""):
            with self.subTest(body=body):
                response = self.client.put(
                    f"/budgets/2026-10/{self.food['id']}", data=body,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

        response = self.client.put(
            f"/budgets/2026-10/{self.food['id']}",
            data='{"amount":"200.00"}', content_type="text/plain",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.list_budgets(), [])

    def test_put_uses_url_identity_and_ignores_identity_fields_in_body(self):
        other = self.create_category("Prevoz")
        response = self.client.put(
            f"/budgets/2026-10/{self.food['id']}",
            json={"amount": "200.00", "month": "2026-11", "category_id": other["id"]},
        )

        self.assertEqual(response.status_code, 201)
        created = response.get_json()
        self.assertEqual(created["month"], "2026-10")
        self.assertEqual(created["category_id"], self.food["id"])
        self.assertEqual(self.list_budgets(), [created])
        self.assertEqual(self.list_budgets("2026-11"), [])

    def test_put_requires_existing_category(self):
        for category_id in (0, 999, 2147483648, 10 ** 100):
            with self.subTest(category_id=category_id):
                response = self.client.put(
                    f"/budgets/2026-10/{category_id}", json={"amount": "200.00"}
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.get_json(), {"error": "Category not found"})
        self.assertEqual(self.list_budgets(), [])

    def test_delete_removes_only_requested_budget(self):
        original = self.set_budget()
        other_month = self.set_budget(month="2026-11")

        response = self.client.delete(f"/budgets/2026-10/{self.food['id']}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.list_budgets(), [])
        self.assertEqual(self.list_budgets("2026-11"), [other_month])
        self.assertIsNone(db.session.get(Budget, original["id"]))
        self.assertIsNotNone(db.session.get(Category, self.food["id"]))

    def test_delete_missing_budget_returns_404(self):
        for category_id in (self.food["id"], 999):
            with self.subTest(category_id=category_id):
                response = self.client.delete(f"/budgets/2026-10/{category_id}")
                self.assertEqual(response.status_code, 404)
                self.assertIn("error", response.get_json())

    def test_category_deletion_cascades_its_budgets_across_months(self):
        other = self.create_category("Prevoz")
        october = self.set_budget()
        november = self.set_budget(month="2026-11")
        kept = self.set_budget(category_id=other["id"])
        stored = db.session.get(Budget, october["id"])
        self.assertEqual(stored.category.id, self.food["id"])

        response = self.client.delete(f"/categories/{self.food['id']}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.list_budgets(), [kept])
        self.assertEqual(self.list_budgets("2026-11"), [])
        for budget_id in (october["id"], november["id"]):
            self.assertIsNone(db.session.get(Budget, budget_id))
        self.assertIsNotNone(db.session.get(Category, other["id"]))

    def test_category_with_transactions_keeps_budgets_when_delete_is_rejected(self):
        october = self.set_budget()
        november = self.set_budget(month="2026-11")
        response = self.client.post("/transactions", json={
            "type": "expense", "amount": "12.50", "date": "2026-10-27",
            "category_id": self.food["id"],
        })
        self.assertEqual(response.status_code, 201)
        transaction_id = response.get_json()["id"]

        rejected = self.client.delete(f"/categories/{self.food['id']}")

        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.list_budgets(), [october])
        self.assertEqual(self.list_budgets("2026-11"), [november])
        self.assertEqual(self.client.get(f"/transactions/{transaction_id}").status_code, 200)

        self.assertEqual(self.client.delete(f"/transactions/{transaction_id}").status_code, 204)
        self.assertEqual(self.client.delete(f"/categories/{self.food['id']}").status_code, 204)
        self.assertEqual(self.list_budgets(), [])
        self.assertEqual(self.list_budgets("2026-11"), [])

    def test_database_rejects_duplicate_category_and_month(self):
        original = self.set_budget()
        db.session.add(Budget(
            month=date(2026, 10, 1), amount=Decimal("250.00"),
            category_id=self.food["id"],
        ))

        with self.assertRaises(IntegrityError) as caught:
            db.session.commit()

        self.assertEqual(caught.exception.orig.diag.constraint_name, "uq_budget_category_month")
        db.session.rollback()
        self.assertEqual(self.list_budgets(), [original])

    def test_rejected_database_delete_preserves_budgets_after_precheck_misses_transaction(self):
        original = self.set_budget()
        transaction = self.client.post("/transactions", json={
            "type": "expense", "amount": "12.50", "date": "2026-10-27",
            "category_id": self.food["id"],
        }).get_json()
        real_execute = db.session.execute

        def miss_transaction_select(statement, *args, **kwargs):
            if statement.is_select:
                result = Mock()
                result.scalar_one_or_none.return_value = None
                return result
            return real_execute(statement, *args, **kwargs)

        # Ako se transakcija pojavi posle provere, baza i dalje stiti sve podatke.
        with patch.object(db.session, "execute", side_effect=miss_transaction_select):
            response = self.client.delete(f"/categories/{self.food['id']}")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.list_budgets(), [original])
        self.assertEqual(
            self.client.get(f"/transactions/{transaction['id']}").get_json(), transaction
        )
        self.set_budget(amount="250.00", status=200)

    def test_unique_conflict_after_precheck_returns_409_and_rolls_back(self):
        original = self.set_budget()
        with patch.object(db.session, "execute") as execute:
            execute.return_value.scalar_one_or_none.return_value = None
            response = self.client.put(
                f"/budgets/2026-10/{self.food['id']}", json={"amount": "250.00"}
            )
            execute.assert_called_once()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json(), {"error": "Budget already exists for this category and month"})
        self.assertEqual(self.list_budgets(), [original])
        self.set_budget(month="2026-11")

    def test_missing_category_at_commit_returns_404_and_rolls_back(self):
        real_get = db.session.get
        category = real_get(Category, self.food["id"])

        def category_before_deletion(model, record_id, *args, **kwargs):
            if model is Category and record_id == 999:
                return category
            return real_get(model, record_id, *args, **kwargs)

        with patch.object(db.session, "get", side_effect=category_before_deletion):
            response = self.client.put("/budgets/2026-10/999", json={"amount": "200.00"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Category not found"})
        self.assertEqual(self.list_budgets(), [])
        self.set_budget()

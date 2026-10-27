from datetime import date
from decimal import Decimal

from tests import BaseTestCase
from app import db
from app.models import Budget, Category, Transaction


class MonthlySummaryTests(BaseTestCase):
    def create_category(self, name="Hrana"):
        category = Category(name=name, color="#123456")
        db.session.add(category)
        db.session.commit()
        return category.id

    def add_transaction(self, category_id, amount, transaction_type="expense", day=date(2026, 10, 10)):
        transaction = Transaction(
            category_id=category_id, amount=Decimal(amount), type=transaction_type,
            date=day, description="Primer",
        )
        db.session.add(transaction)
        db.session.commit()
        return transaction.id

    def add_budget(self, category_id, amount, month=date(2026, 10, 1)):
        budget = Budget(category_id=category_id, amount=Decimal(amount), month=month)
        db.session.add(budget)
        db.session.commit()
        return budget.id

    def get_summary(self, month="2026-10", **params):
        response = self.client.get("/summary", query_string={"month": month, **params})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_empty_month_returns_zero_totals_and_no_categories(self):
        self.create_category()

        self.assertEqual(self.get_summary(), {
            "month": "2026-10", "total_income": "0.00", "total_expense": "0.00",
            "balance": "0.00", "categories": [],
        })

    def test_income_only_counts_in_totals_but_does_not_add_category(self):
        salary = self.create_category("Plata")
        self.add_transaction(salary, "300.00", "income")

        self.assertEqual(self.get_summary(), {
            "month": "2026-10", "total_income": "300.00", "total_expense": "0.00",
            "balance": "300.00", "categories": [],
        })

    def test_budget_only_category_is_included_without_changing_totals(self):
        food = self.create_category()
        self.add_budget(food, "200.00")

        data = self.get_summary()

        self.assertEqual(data["total_income"], "0.00")
        self.assertEqual(data["total_expense"], "0.00")
        self.assertEqual(data["balance"], "0.00")
        self.assertEqual(data["categories"], [{
            "category_id": food, "category_name": "Hrana", "spent": "0.00",
            "budget": "200.00", "remaining": "200.00",
        }])

    def test_expense_without_budget_uses_zero_budget_and_negative_remaining(self):
        food = self.create_category()
        self.add_transaction(food, "12.50")

        data = self.get_summary()

        self.assertEqual(data["total_expense"], "12.50")
        self.assertEqual(data["balance"], "-12.50")
        self.assertEqual(data["categories"], [{
            "category_id": food, "category_name": "Hrana", "spent": "12.50",
            "budget": "0.00", "remaining": "-12.50",
        }])

    def test_income_with_budget_is_included_but_income_is_not_spending(self):
        salary = self.create_category("Plata")
        self.add_transaction(salary, "300.00", "income")
        self.add_budget(salary, "100.00")

        data = self.get_summary()

        self.assertEqual(data["total_income"], "300.00")
        self.assertEqual(data["total_expense"], "0.00")
        self.assertEqual(data["categories"], [{
            "category_id": salary, "category_name": "Plata", "spent": "0.00",
            "budget": "100.00", "remaining": "100.00",
        }])

    def test_multiple_transactions_are_summed_without_multiplying_budgets(self):
        food = self.create_category()
        transport = self.create_category("Prevoz")
        self.add_transaction(food, "100.00", "income")
        self.add_transaction(food, "50.00", "income")
        for amount in ("10.00", "20.00", "30.00"):
            self.add_transaction(food, amount)
        self.add_transaction(transport, "15.00")
        self.add_budget(food, "100.00")
        self.add_budget(transport, "50.00")

        data = self.get_summary()

        self.assertEqual(data["total_income"], "150.00")
        self.assertEqual(data["total_expense"], "75.00")
        self.assertEqual(data["balance"], "75.00")
        self.assertEqual(data["categories"], [
            {"category_id": food, "category_name": "Hrana", "spent": "60.00",
             "budget": "100.00", "remaining": "40.00"},
            {"category_id": transport, "category_name": "Prevoz", "spent": "15.00",
             "budget": "50.00", "remaining": "35.00"},
        ])

    def test_balance_and_remaining_can_both_be_negative(self):
        food = self.create_category()
        self.add_transaction(food, "10.00", "income")
        self.add_transaction(food, "100.00")
        self.add_budget(food, "60.00")

        data = self.get_summary()

        self.assertEqual(data["balance"], "-90.00")
        self.assertEqual(data["categories"][0]["remaining"], "-40.00")

    def test_decimal_sums_and_zero_balance_are_exact(self):
        food = self.create_category()
        for amount in ("0.10", "0.20"):
            self.add_transaction(food, amount, "income")
            self.add_transaction(food, amount)
        self.add_budget(food, "1.00")

        data = self.get_summary()

        self.assertEqual(data["total_income"], "0.30")
        self.assertEqual(data["total_expense"], "0.30")
        self.assertEqual(data["balance"], "0.00")
        self.assertEqual(data["categories"][0]["spent"], "0.30")
        self.assertEqual(data["categories"][0]["remaining"], "0.70")

    def test_aggregate_totals_can_exceed_single_transaction_amount_limit(self):
        food = self.create_category()
        for _ in range(3):
            self.add_transaction(food, "1000000.00", "income")
        for _ in range(2):
            self.add_transaction(food, "1000000.00")
        self.add_budget(food, "1000000.00")

        data = self.get_summary()

        self.assertEqual(data["total_income"], "3000000.00")
        self.assertEqual(data["total_expense"], "2000000.00")
        self.assertEqual(data["balance"], "1000000.00")
        self.assertEqual(data["categories"][0]["spent"], "2000000.00")
        self.assertEqual(data["categories"][0]["remaining"], "-1000000.00")

    def test_categories_are_ordered_by_spending_then_name(self):
        leisure = self.create_category("Zabava")
        food = self.create_category("Hrana")
        car = self.create_category("Auto")
        budget_only = self.create_category("Samo budzet")
        self.create_category("Neiskoriscena")
        for category_id, amount in ((leisure, "50.00"), (food, "50.00"), (car, "75.00")):
            self.add_transaction(category_id, amount)
        self.add_budget(budget_only, "100.00")

        data = self.get_summary()

        self.assertEqual(
            [row["category_id"] for row in data["categories"]],
            [car, food, leisure, budget_only],
        )

    def test_only_selected_month_contributes_and_both_boundary_days_are_included(self):
        food = self.create_category()
        self.add_transaction(food, "999.00", day=date(2026, 9, 30))
        self.add_transaction(food, "100.00", "income", date(2026, 10, 1))
        self.add_transaction(food, "25.00", day=date(2026, 10, 31))
        self.add_transaction(food, "888.00", day=date(2026, 11, 1))
        self.add_budget(food, "1000.00", date(2026, 9, 1))
        self.add_budget(food, "50.00")
        self.add_budget(food, "1000.00", date(2026, 11, 1))

        data = self.get_summary()

        self.assertEqual(data["total_income"], "100.00")
        self.assertEqual(data["total_expense"], "25.00")
        self.assertEqual(data["balance"], "75.00")
        self.assertEqual(data["categories"][0]["budget"], "50.00")
        self.assertEqual(data["categories"][0]["remaining"], "25.00")

    def test_leap_february_includes_last_day_and_excludes_march(self):
        food = self.create_category()
        self.add_transaction(food, "10.00", day=date(2024, 2, 1))
        self.add_transaction(food, "20.00", day=date(2024, 2, 29))
        self.add_transaction(food, "30.00", day=date(2024, 3, 1))

        data = self.get_summary("2024-02")

        self.assertEqual(data["month"], "2024-02")
        self.assertEqual(data["total_expense"], "30.00")

    def test_minimum_year_and_maximum_december_do_not_overflow(self):
        first = self.create_category("Prvi")
        last = self.create_category("Poslednji")
        cases = (
            ("0001-01", first, date(1, 1, 1), date(1, 1, 31)),
            ("9999-12", last, date(9999, 12, 1), date(9999, 12, 31)),
        )
        for _, category_id, start, end in cases:
            self.add_budget(category_id, "3.00", start)
            self.add_transaction(category_id, "2.00", "income", start)
            self.add_transaction(category_id, "1.25", day=end)

        for month, category_id, _, _ in cases:
            with self.subTest(month=month):
                data = self.get_summary(month)
                self.assertEqual(data["month"], month)
                self.assertEqual(data["total_income"], "2.00")
                self.assertEqual(data["total_expense"], "1.25")
                self.assertEqual(data["balance"], "0.75")
                self.assertEqual(data["categories"][0]["category_id"], category_id)
                self.assertEqual(data["categories"][0]["remaining"], "1.75")

    def test_month_with_data_only_elsewhere_still_returns_empty_summary(self):
        food = self.create_category()
        self.add_transaction(food, "20.00", day=date(2026, 9, 30))
        self.add_budget(food, "100.00", date(2026, 11, 1))

        data = self.get_summary()

        self.assertEqual(data["categories"], [])
        self.assertEqual(data["total_income"], "0.00")
        self.assertEqual(data["total_expense"], "0.00")
        self.assertEqual(data["balance"], "0.00")

    def test_month_is_required_and_invalid_or_repeated_month_is_rejected(self):
        invalid_queries = (
            {}, {"month": ""}, {"month": "2026-00"}, {"month": "2026-13"},
            {"month": "0000-01"}, {"month": "10000-01"}, {"month": "2026-1"},
            {"month": "202610"}, {"month": "2026-10-01"},
            {"month": "2026-10 "}, {"month": "invalid"},
        )
        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get("/summary", query_string=query)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

        repeated = self.client.get(
            "/summary", query_string=[("month", "2026-10"), ("month", "2026-11")]
        )
        self.assertEqual(repeated.status_code, 400)
        self.assertIn("error", repeated.get_json())

    def test_unknown_query_parameters_are_ignored(self):
        food = self.create_category()
        self.add_transaction(food, "20.00", "income")

        self.assertEqual(self.get_summary(unused="ignored"), self.get_summary())

    def test_summary_does_not_change_any_saved_rows_or_ids(self):
        food = self.create_category()
        self.add_transaction(food, "20.00", "income")
        self.add_transaction(food, "12.50")
        self.add_budget(food, "100.00")

        def snapshot():
            result = {}
            for model in (Category, Transaction, Budget):
                table = model.__table__
                result[table.name] = db.session.execute(
                    db.select(table).order_by(table.c.id)
                ).all()
            return result

        before = snapshot()

        self.get_summary()
        self.get_summary("2026-11")

        self.assertEqual(snapshot(), before)

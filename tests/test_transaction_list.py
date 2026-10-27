from datetime import date
from decimal import Decimal

from tests import BaseTestCase
from app import db
from app.models import Category, Transaction


class TransactionListTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.food = Category(name="Hrana", color="#123456")
        self.work = Category(name="Posao", color="#FFFFFF")
        db.session.add_all([self.food, self.work])
        db.session.commit()

    def create_transaction(self, **changes):
        values = {
            "type": "expense",
            "amount": Decimal("12.50"),
            "date": date(2026, 10, 10),
            "description": "Rucak",
            "category_id": self.food.id,
        }
        values.update(changes)
        transaction = Transaction(**values)
        db.session.add(transaction)
        db.session.commit()
        return transaction

    def get_list(self, **params):
        response = self.client.get("/transactions", query_string=params)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def assert_item_ids(self, data, expected):
        self.assertEqual([item["id"] for item in data["items"]], expected)

    def test_empty_list_has_default_pagination(self):
        self.assertEqual(self.get_list(), {
            "items": [], "page": 1, "per_page": 20, "total": 0, "pages": 0,
        })

    def test_items_use_same_response_format_as_single_transaction(self):
        transaction = self.create_transaction(description=None)

        data = self.get_list()

        self.assertEqual(data["items"], [transaction.to_dict()])
        self.assertEqual(data["items"][0]["amount"], "12.50")
        self.assertEqual(data["items"][0]["date"], "2026-10-10")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["pages"], 1)

    def test_default_page_contains_at_most_twenty_transactions(self):
        transactions = [self.create_transaction() for _ in range(21)]

        data = self.get_list()

        self.assert_item_ids(data, [item.id for item in reversed(transactions[1:])])
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["per_page"], 20)
        self.assertEqual(data["total"], 21)
        self.assertEqual(data["pages"], 2)

    def test_order_is_newest_date_then_last_added_first(self):
        first = self.create_transaction(date=date(2026, 10, 27))
        older = self.create_transaction(date=date(2026, 10, 8))
        second = self.create_transaction(date=date(2026, 10, 27))
        third = self.create_transaction(date=date(2026, 10, 27))

        self.assert_item_ids(self.get_list(), [third.id, second.id, first.id, older.id])

    def test_update_does_not_change_order_for_same_date(self):
        first = self.create_transaction()
        second = self.create_transaction()

        response = self.client.put(
            f"/transactions/{first.id}", json={"description": "Izmenjen opis"}
        )

        self.assertEqual(response.status_code, 200)
        self.assert_item_ids(self.get_list(), [second.id, first.id])

    def test_date_range_includes_both_boundary_dates(self):
        self.create_transaction(date=date(2026, 10, 8))
        lower = self.create_transaction(date=date(2026, 10, 9))
        middle = self.create_transaction(date=date(2026, 10, 10))
        upper = self.create_transaction(date=date(2026, 10, 11))
        self.create_transaction(date=date(2026, 10, 12))

        data = self.get_list(date_from="2026-10-09", date_to="2026-10-11")

        self.assert_item_ids(data, [upper.id, middle.id, lower.id])
        self.assertEqual(data["total"], 3)
        same_day = self.get_list(date_from="2026-10-10", date_to="2026-10-10")
        self.assert_item_ids(same_day, [middle.id])

    def test_each_date_boundary_can_be_used_separately(self):
        older = self.create_transaction(date=date(2026, 10, 9))
        boundary = self.create_transaction(date=date(2026, 10, 10))
        newer = self.create_transaction(date=date(2026, 10, 11))

        cases = (
            ({"date_from": "2026-10-10"}, [newer.id, boundary.id]),
            ({"date_to": "2026-10-10"}, [boundary.id, older.id]),
        )
        for params, expected in cases:
            with self.subTest(params=params):
                self.assert_item_ids(self.get_list(**params), expected)

    def test_filter_by_category(self):
        food = self.create_transaction()
        self.create_transaction(category_id=self.work.id)

        data = self.get_list(category_id=self.food.id)

        self.assert_item_ids(data, [food.id])
        self.assertEqual(data["total"], 1)

    def test_filter_by_type(self):
        expense = self.create_transaction()
        income = self.create_transaction(type="income")

        for transaction_type, expected in (
            ("expense", [expense.id]), ("income", [income.id]),
        ):
            with self.subTest(type=transaction_type):
                self.assert_item_ids(self.get_list(type=transaction_type), expected)

    def test_all_filters_must_match_the_same_transaction(self):
        expected = self.create_transaction(description="Rucak i kafa")
        self.create_transaction(date=date(2026, 10, 11))
        self.create_transaction(category_id=self.work.id)
        self.create_transaction(type="income")
        self.create_transaction(description="Namirnice")

        data = self.get_list(
            date_from="2026-10-09", date_to="2026-10-10",
            category_id=self.food.id, type="expense", search="rUcAk",
        )

        self.assert_item_ids(data, [expected.id])
        self.assertEqual(data["total"], 1)

    def test_search_is_case_insensitive_substring_and_excludes_null(self):
        expected = self.create_transaction(description="Rucak i kafa")
        self.create_transaction(description="Samo kafa")
        self.create_transaction(description=None)

        self.assert_item_ids(self.get_list(search="UCAK"), [expected.id])

    def test_search_treats_sql_wildcards_and_escape_characters_literally(self):
        cases = (
            ("%", "Popust 10%"),
            ("_", "oznaka_123"),
            ("/", "putanja/a"),
            ("\\", "putanja\\a"),
        )
        expected = {}
        for search, description in cases:
            expected[search] = self.create_transaction(description=description).id
        self.create_transaction(description="Obican opis")

        for search, _ in cases:
            with self.subTest(search=search):
                data = self.get_list(search=search)
                self.assert_item_ids(data, [expected[search]])
                self.assertEqual(data["total"], 1)

    def test_empty_search_is_ignored_and_spaces_are_preserved(self):
        no_description = self.create_transaction(description=None)
        with_space = self.create_transaction(description=" ")
        no_space = self.create_transaction(description="Rucak")

        self.assert_item_ids(
            self.get_list(search=""), [no_space.id, with_space.id, no_description.id]
        )
        self.assert_item_ids(self.get_list(search=" "), [with_space.id])

    def test_valid_filters_without_matches_return_empty_list(self):
        self.create_transaction()

        for params in (
            {"category_id": 999}, {"category_id": 2147483647},
            {"type": "income"}, {"search": "ne postoji"},
        ):
            with self.subTest(params=params):
                data = self.get_list(**params)
                self.assertEqual(data["items"], [])
                self.assertEqual(data["total"], 0)
                self.assertEqual(data["pages"], 0)

    def test_pages_have_no_overlap_and_last_page_can_be_shorter(self):
        transactions = [self.create_transaction() for _ in range(5)]
        expected_pages = (
            [transactions[4].id, transactions[3].id],
            [transactions[2].id, transactions[1].id],
            [transactions[0].id],
        )

        for page, expected in enumerate(expected_pages, start=1):
            with self.subTest(page=page):
                data = self.get_list(page=page, per_page=2)
                self.assert_item_ids(data, expected)
                self.assertEqual(data["page"], page)
                self.assertEqual(data["per_page"], 2)
                self.assertEqual(data["total"], 5)
                self.assertEqual(data["pages"], 3)

    def test_filter_is_applied_before_pagination_and_total_count(self):
        expected = [self.create_transaction() for _ in range(4)]
        for _ in range(3):
            self.create_transaction(category_id=self.work.id)

        data = self.get_list(category_id=self.food.id, page=2, per_page=2)

        self.assert_item_ids(data, [expected[1].id, expected[0].id])
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["pages"], 2)

    def test_page_beyond_last_returns_empty_items_with_correct_totals(self):
        self.create_transaction()

        for page in (2, 2147483647):
            with self.subTest(page=page):
                data = self.get_list(page=page, per_page=1)
                self.assertEqual(data, {
                    "items": [], "page": page, "per_page": 1,
                    "total": 1, "pages": 1,
                })

    def test_maximum_page_size_is_accepted(self):
        transaction = self.create_transaction()

        data = self.get_list(per_page=100)

        self.assert_item_ids(data, [transaction.id])
        self.assertEqual(data["per_page"], 100)

    def test_invalid_pagination_returns_400(self):
        common_invalid = ("", "0", "-1", "abc", "true", "1.0", "+1", " 1", "１")
        cases = {
            "page": common_invalid + ("2147483648", "9" * 4500),
            "per_page": common_invalid + ("101", "9" * 4500),
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value[:30]):
                    response = self.client.get(
                        "/transactions", query_string={field: value}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())

    def test_invalid_date_filters_return_400(self):
        invalid = (
            "", "2026-02-29", "2026-13-01", "0000-01-01",
            "20261027", "2026-W44-2", "2026-1-01",
        )
        for field in ("date_from", "date_to"):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    response = self.client.get(
                        "/transactions", query_string={field: value}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())

    def test_reversed_date_range_returns_400(self):
        response = self.client.get("/transactions", query_string={
            "date_from": "2026-10-11", "date_to": "2026-10-10",
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_invalid_category_and_type_filters_return_400(self):
        cases = {
            "category_id": ("", "0", "-1", "abc", "true", "1.0", "2147483648"),
            "type": ("", "Income", "EXPENSE", "other", "null"),
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    response = self.client.get(
                        "/transactions", query_string={field: value}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("error", response.get_json())

    def test_duplicate_supported_parameters_return_400(self):
        values = {
            "date_from": "2026-10-01", "date_to": "2026-10-31",
            "category_id": str(self.food.id), "type": "expense",
            "search": "Rucak", "page": "1", "per_page": "20",
        }
        for field, value in values.items():
            with self.subTest(field=field):
                response = self.client.get(
                    "/transactions", query_string=[(field, value), (field, value)]
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    def test_search_with_nul_returns_400(self):
        response = self.client.get(
            "/transactions", query_string={"search": "Rucak\x00"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_unknown_parameters_are_ignored(self):
        transaction = self.create_transaction()

        self.assert_item_ids(self.get_list(unknown="ignored"), [transaction.id])

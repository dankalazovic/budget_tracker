import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from pydantic import ValidationError

from app.schemas import (
    CategoryCreate,
    CategoryResponse,
    TransactionFilters,
    TransactionInput,
    TransactionListResponse,
    TransactionResponse,
)


class SchemaTests(unittest.TestCase):
    def transaction_data(self, **changes):
        values = {
            "type": "expense",
            "amount": "12.50",
            "date": "2026-10-27",
            "description": "Rucak",
            "category_id": 1,
        }
        values.update(changes)
        return values

    def test_category_schema_trims_name_and_keeps_strict_strings(self):
        category = CategoryCreate.model_validate({
            "name": "  Hrana  ", "color": "#aBc123", "ignored": "value",
        })
        self.assertEqual(category.model_dump(), {"name": "Hrana", "color": "#aBc123"})

        for field in ("name", "color"):
            for value in (True, 123, [], {}, None):
                with self.subTest(field=field, value=value):
                    values = {"name": "Hrana", "color": "#123456", field: value}
                    with self.assertRaises(ValidationError):
                        CategoryCreate.model_validate(values)

    def test_category_schema_enforces_length_color_and_valid_text(self):
        for name in ("", "  ", "A" * 31, "Hrana\x00", "Hrana\ud800"):
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    CategoryCreate.model_validate({"name": name, "color": "#123456"})
        for color in ("#123", "red", "#GG0000", "#123456\n"):
            with self.subTest(color=color):
                with self.assertRaises(ValidationError):
                    CategoryCreate.model_validate({"name": "Hrana", "color": color})

    def test_transaction_schema_returns_typed_values_and_enforces_amount_rules(self):
        transaction = TransactionInput.model_validate(self.transaction_data())
        self.assertEqual(transaction.amount, Decimal("12.50"))
        self.assertEqual(transaction.date, date(2026, 10, 27))
        self.assertEqual(transaction.type, "expense")

        invalid_amounts = (
            True, False, None, "0", "-1", "1000000.01", "12.345", "12.500",
            "NaN", "Infinity", "1_0", " 12.50 ",
        )
        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                with self.assertRaises(ValidationError):
                    TransactionInput.model_validate(self.transaction_data(amount=amount))

    def test_transaction_schema_rejects_coerced_ids_and_non_calendar_dates(self):
        for category_id in (True, False, "1", 1.0, 0, -1, 2147483648):
            with self.subTest(category_id=category_id):
                with self.assertRaises(ValidationError):
                    TransactionInput.model_validate(self.transaction_data(category_id=category_id))
        for value in (0, 20261027, "2026-02-29", "20261027", "2026-10-27T00:00:00"):
            with self.subTest(date=value):
                with self.assertRaises(ValidationError):
                    TransactionInput.model_validate(self.transaction_data(date=value))

    def test_description_is_optional_but_is_not_coerced_or_trimmed(self):
        for value, expected in ((None, None), ("", None), ("  Rucak  ", "  Rucak  "), ("A" * 200, "A" * 200)):
            with self.subTest(description=value):
                result = TransactionInput.model_validate(self.transaction_data(description=value))
                self.assertEqual(result.description, expected)
        for value in (True, 123, "A" * 201, "Opis\x00", "Opis\udfff"):
            with self.subTest(description=value):
                with self.assertRaises(ValidationError):
                    TransactionInput.model_validate(self.transaction_data(description=value))

    def test_response_schemas_serialize_attributes_dates_decimals_and_null(self):
        category = SimpleNamespace(id=1, name="Hrana", color="#123456")
        self.assertEqual(
            CategoryResponse.model_validate(category).model_dump(mode="json"),
            {"id": 1, "name": "Hrana", "color": "#123456"},
        )
        transaction = SimpleNamespace(
            id=7, type="expense", amount=Decimal("12.5"),
            date=date(2026, 10, 27), description=None, category_id=1,
        )
        expected = {
            "id": 7, "type": "expense", "amount": "12.50", "date": "2026-10-27",
            "description": None, "category_id": 1,
        }
        self.assertEqual(
            TransactionResponse.model_validate(transaction).model_dump(mode="json"), expected
        )
        page = TransactionListResponse.model_validate({
            "items": [transaction], "page": 1, "per_page": 20, "total": 1, "pages": 1,
        })
        self.assertEqual(page.model_dump(mode="json")["items"], [expected])

    def test_required_fields_reject_explicit_null_but_valid_defaults_can_be_merged(self):
        saved = TransactionInput.model_validate(self.transaction_data()).model_dump()
        unchanged = TransactionInput.model_validate(saved)
        self.assertEqual(unchanged.amount, Decimal("12.50"))
        for field in ("type", "amount", "date", "category_id"):
            with self.subTest(field=field):
                values = dict(saved, **{field: None})
                with self.assertRaises(ValidationError):
                    TransactionInput.model_validate(values)

    def test_filter_schema_converts_query_strings_and_checks_date_range(self):
        filters = TransactionFilters.model_validate({
            "page": "2", "per_page": "10", "category_id": "1", "type": "expense",
            "date_from": "2026-10-01", "date_to": "2026-10-31", "search": " Rucak ",
        })
        self.assertEqual((filters.page, filters.per_page, filters.category_id), (2, 10, 1))
        self.assertEqual(filters.date_from, date(2026, 10, 1))
        self.assertEqual(filters.search, " Rucak ")
        for invalid in (
            {"page": "0"}, {"page": "true"}, {"per_page": "101"},
            {"category_id": "1.0"}, {"date_from": "20261027"},
            {"date_from": "2026-11-01", "date_to": "2026-10-01"},
        ):
            with self.subTest(query=invalid):
                with self.assertRaises(ValidationError):
                    TransactionFilters.model_validate(invalid)

import csv
import json
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from tempfile import TemporaryFile
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import MultiDict

from tests import BaseTestCase
from app import db
from app.models import Category, Transaction


class CsvImportTests(BaseTestCase):
    header = ["type", "amount", "date", "description", "category"]

    def setUp(self):
        super().setUp()
        response = self.client.post(
            "/categories", json={"name": "Hrana", "color": "#123456"}
        )
        self.category_id = response.get_json()["id"]

    def row(self, **changes):
        values = {
            "type": "expense", "amount": "12.50", "date": "2026-10-27",
            "description": "Rucak", "category": "Hrana",
        }
        values.update(changes)
        return [values[field] for field in self.header]

    def csv_bytes(self, rows, header=None):
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(self.header if header is None else header)
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")

    def upload(self, content, filename="transactions.csv"):
        response = self.client.post(
            "/transactions/import",
            data={"file": (BytesIO(content), filename)},
            content_type="multipart/form-data", buffered=True,
        )
        self.addCleanup(response.close)
        return response

    def capture_report_file(self, *args, **kwargs):
        self.report_file = TemporaryFile(*args, **kwargs)
        self.addCleanup(self.report_file.close)
        return self.report_file

    def transactions(self):
        return db.session.execute(
            db.select(Transaction).order_by(Transaction.id)
        ).scalars().all()

    def create_original(self):
        response = self.client.post("/transactions", json={
            "type": "income", "amount": "900.00", "date": "2026-09-01",
            "description": "Postojeca", "category_id": self.category_id,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_import_stores_exact_values_and_existing_category(self):
        response = self.upload(self.csv_bytes([
            self.row(), self.row(type="income", amount="1000000.00", description=""),
            self.row(amount="0.01", date="2024-02-29"),
        ]))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json(), {"imported": 3, "failed": 0, "errors": []})
        records = self.transactions()
        self.assertEqual(records[0].amount, Decimal("12.50"))
        self.assertEqual(records[0].date, date(2026, 10, 27))
        self.assertEqual(records[0].description, "Rucak")
        self.assertEqual(records[0].category_id, self.category_id)
        self.assertEqual(records[1].amount, Decimal("1000000.00"))
        self.assertEqual(records[1].type, "income")
        self.assertIsNone(records[1].description)
        self.assertEqual(records[2].date, date(2024, 2, 29))
        self.assertEqual(db.session.scalar(db.select(db.func.count(Category.id))), 1)

    def test_optional_description_reordered_trimmed_header_and_bom(self):
        header = [" category ", " date ", "amount", "type"]
        content = self.csv_bytes([["  hRaNa  ", "2026-10-27", "3.10", "expense"]], header)

        response = self.upload(b"\xef\xbb\xbf" + content)

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json(), {"imported": 1, "failed": 0, "errors": []})
        record = self.transactions()[0]
        self.assertEqual(record.category_id, self.category_id)
        self.assertIsNone(record.description)

    def test_unicode_category_name_is_resolved_case_insensitively(self):
        response = self.client.post(
            "/categories", json={"name": "Članarina", "color": "#ABCDEF"}
        )
        category_id = response.get_json()["id"]

        response = self.upload(self.csv_bytes([self.row(category="čLANARINA")]))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["imported"], 1)
        self.assertEqual(self.transactions()[0].category_id, category_id)

    def test_quoted_comma_newline_and_quotes_preserve_description(self):
        description = 'Ručak, kafa\n"Restoran"'

        response = self.upload(self.csv_bytes([self.row(description=description)]))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.transactions()[0].description, description)

    def test_partial_import_reports_errors_in_logical_record_order(self):
        rows = [
            self.row(description="Prvi\nsa novim redom"),
            self.row(amount="0"),
            self.row(category="Nepostojeca"),
            self.row(type="income", amount="40.00"),
            self.row(date="2026-02-29"),
            self.row()[:-1],
            self.row(description="Poslednji"),
        ]

        with patch("app.services.csv_import.CSV_BATCH_SIZE", 2):
            response = self.upload(self.csv_bytes(rows))

        self.assertEqual(response.status_code, 200, response.get_json())
        report = response.get_json()
        self.assertEqual(report["imported"], 3)
        self.assertEqual(report["failed"], 4)
        self.assertEqual([item["row"] for item in report["errors"]], [3, 4, 6, 7])
        self.assertTrue(all(item["error"] for item in report["errors"]))
        self.assertEqual(len(self.transactions()), 3)

    def test_blank_records_and_wrong_column_count_are_row_errors(self):
        content = self.csv_bytes([self.row()]) + b"\nexpense,1.00,2026-10-27\n"
        content += self.csv_bytes([self.row() + ["extra"]], header=[]).split(b"\r\n", 1)[1]

        response = self.upload(content)

        self.assertEqual(response.status_code, 200, response.get_json())
        report = response.get_json()
        self.assertEqual(report["imported"], 1)
        self.assertEqual(report["failed"], 3)
        self.assertEqual([item["row"] for item in report["errors"]], [3, 4, 5])

    def test_csv_reuses_transaction_validation_messages(self):
        invalid_values = {
            "type": ["Income", "other", ""],
            "amount": ["NaN", "Infinity", "0", "-1", "1000000.01", "12.345", "12.500", " 12.50 ", "1e2"],
            "date": ["2026-02-29", "2026-1-01", "0000-01-01", "2026-10-27T12:00:00"],
            "description": ["A" * 201, "Opis\x00"],
        }
        for field, values in invalid_values.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    data = dict(zip(self.header, self.row(**{field: value})))
                    data.pop("category")
                    data["category_id"] = self.category_id
                    api_response = self.client.post("/transactions", json=data)
                    self.assertEqual(api_response.status_code, 400)

                    response = self.upload(self.csv_bytes([self.row(**{field: value})]))

                    self.assertEqual(response.status_code, 200, response.get_json())
                    self.assertEqual(response.get_json(), {
                        "imported": 0, "failed": 1,
                        "errors": [{"row": 2, "error": api_response.get_json()["error"]}],
                    })
        self.assertEqual(self.transactions(), [])

    def test_invalid_or_unknown_category_is_a_row_error_not_created(self):
        response = self.upload(self.csv_bytes([
            self.row(category=""), self.row(category=" " * 3),
            self.row(category="A" * 31), self.row(category="Hra\x00na"),
            self.row(category="Nova"),
        ]))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["imported"], 0)
        self.assertEqual(response.get_json()["failed"], 5)
        self.assertEqual([item["row"] for item in response.get_json()["errors"]], [2, 3, 4, 5, 6])
        self.assertEqual(self.transactions(), [])
        self.assertEqual(db.session.scalar(db.select(db.func.count(Category.id))), 1)

    def test_header_only_is_an_empty_successful_import(self):
        response = self.upload(self.csv_bytes([]))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json(), {"imported": 0, "failed": 0, "errors": []})
        self.assertEqual(self.transactions(), [])

    def test_invalid_headers_reject_entire_file(self):
        original = self.create_original()
        headers = [
            ["type", "amount", "date", "description"],
            self.header + ["unknown"],
            self.header + ["amount"],
            self.header + [" amount "],
            self.header + [""],
            [],
        ]
        for header in headers:
            with self.subTest(header=header):
                response = self.upload(self.csv_bytes([self.row()], header))

                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertIn("error", response.get_json())
                self.assertEqual(len(self.transactions()), 1)
                self.assertEqual(
                    self.client.get(f"/transactions/{original['id']}").get_json(), original
                )

    def test_missing_empty_or_multiple_uploads_are_rejected(self):
        valid = self.csv_bytes([self.row()])
        bodies = [
            {},
            {"other": (BytesIO(valid), "other.csv")},
            {"file": (BytesIO(valid), "")},
            {"file": (BytesIO(b""), "empty.csv")},
            MultiDict([
                ("file", (BytesIO(valid), "first.csv")),
                ("file", (BytesIO(valid), "second.csv")),
            ]),
            {
                "file": (BytesIO(valid), "first.csv"),
                "other": (BytesIO(valid), "second.csv"),
            },
        ]
        for index, body in enumerate(bodies):
            with self.subTest(index=index):
                response = self.client.post(
                    "/transactions/import", data=body,
                    content_type="multipart/form-data", buffered=True,
                )
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertIn("error", response.get_json())
        self.assertEqual(self.transactions(), [])

    def test_non_multipart_request_is_rejected(self):
        response = self.client.post("/transactions/import", json={"file": "transactions.csv"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())
        self.assertEqual(self.transactions(), [])

    def test_invalid_utf8_after_valid_rows_does_not_import_anything(self):
        original = self.create_original()
        content = self.csv_bytes([self.row()] * 4) + b"expense,1,2026-10-27,\xff,Hrana\n"

        with patch("app.services.csv_import.CSV_BATCH_SIZE", 2):
            response = self.upload(content)

        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(len(self.transactions()), 1)
        self.assertEqual(self.client.get(f"/transactions/{original['id']}").get_json(), original)

    def test_unclosed_quote_after_valid_rows_does_not_import_anything(self):
        original = self.create_original()
        content = self.csv_bytes([self.row()] * 4) + b'expense,1,2026-10-27,"unfinished,Hrana\n'

        with patch("app.services.csv_import.CSV_BATCH_SIZE", 2):
            response = self.upload(content)

        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(len(self.transactions()), 1)
        self.assertEqual(self.client.get(f"/transactions/{original['id']}").get_json(), original)

    def test_limit_includes_invalid_records_and_rejects_before_any_insert(self):
        original = self.create_original()
        content = self.csv_bytes([self.row(), self.row(amount="0"), self.row(), self.row()])

        with patch("app.services.csv_import.CSV_MAX_ROWS", 3):
            response = self.upload(content)

        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(len(self.transactions()), 1)
        self.assertEqual(self.client.get(f"/transactions/{original['id']}").get_json(), original)

    def test_exact_limit_is_accepted_and_header_is_not_counted(self):
        with patch("app.services.csv_import.CSV_MAX_ROWS", 3):
            response = self.upload(self.csv_bytes([self.row()] * 3))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json(), {"imported": 3, "failed": 0, "errors": []})
        self.assertEqual(len(self.transactions()), 3)

    def test_fatal_database_error_rolls_back_all_new_batches_only(self):
        original = self.create_original()
        real_execute = db.session.execute
        insert_count = 0

        def fail_second_insert(statement, *args, **kwargs):
            nonlocal insert_count
            if getattr(statement, "is_insert", False) and statement.table.name == "transactions":
                insert_count += 1
                if insert_count == 2:
                    raise SQLAlchemyError("private database details")
            return real_execute(statement, *args, **kwargs)

        with patch("app.services.csv_import.CSV_BATCH_SIZE", 2):
            with patch.object(db.session, "execute", side_effect=fail_second_insert):
                response = self.upload(self.csv_bytes([self.row()] * 4))

        self.assertEqual(insert_count, 2)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error"})
        self.assertEqual(len(self.transactions()), 1)
        self.assertEqual(self.client.get(f"/transactions/{original['id']}").get_json(), original)

    def test_category_disappearing_before_insert_only_fails_affected_row(self):
        original = self.create_original()
        real_execute = db.session.execute
        changed = False

        def invalidate_one_category(statement, parameters=None, *args, **kwargs):
            nonlocal changed
            if getattr(statement, "is_insert", False) and not changed:
                # Simuliramo nestalu kategoriju: pravi PostgreSQL FK odbija upis.
                parameters[1]["category_id"] = 999
                changed = True
            return real_execute(statement, parameters, *args, **kwargs)

        with patch("app.services.csv_import.CSV_BATCH_SIZE", 2):
            with patch.object(db.session, "execute", side_effect=invalidate_one_category):
                response = self.upload(self.csv_bytes([self.row()] * 4))

        self.assertTrue(changed)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json(), {
            "imported": 3, "failed": 1,
            "errors": [{"row": 3, "error": "category: Category not found"}],
        })
        self.assertEqual(len(self.transactions()), 4)
        self.assertEqual(self.client.get(f"/transactions/{original['id']}").get_json(), original)

    def test_original_transaction_and_category_are_preserved_on_partial_success(self):
        original = self.create_original()

        response = self.upload(self.csv_bytes([self.row(), self.row(category="Nema")]))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["imported"], 1)
        self.assertEqual(response.get_json()["failed"], 1)
        self.assertEqual(len(self.transactions()), 2)
        self.assertEqual(self.client.get(f"/transactions/{original['id']}").get_json(), original)
        self.assertIsNotNone(db.session.get(Category, self.category_id))

    def test_description_whitespace_and_length_are_preserved(self):
        descriptions = [" ", "  Rucak  ", "Ž" * 200]

        response = self.upload(self.csv_bytes([self.row(description=text) for text in descriptions]))

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["imported"], 3)
        self.assertEqual([record.description for record in self.transactions()], descriptions)

    def test_report_stream_does_not_need_database_session_after_request(self):
        response = self.client.post(
            "/transactions/import",
            data={"file": (BytesIO(self.csv_bytes([
                self.row(), self.row(amount="0"), self.row(category="Nema"),
            ])), "transactions.csv")},
            content_type="multipart/form-data", buffered=False,
        )
        self.addCleanup(response.close)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_streamed)
        db.session.remove()
        with patch.object(db.session, "execute", side_effect=AssertionError("SQL during report")):
            report = json.loads(b"".join(response.response))

        self.assertEqual(report["imported"], 1)
        self.assertEqual(report["failed"], 2)
        self.assertEqual([item["row"] for item in report["errors"]], [3, 4])
        self.assertEqual(len(self.transactions()), 1)

    def test_report_file_closes_when_response_is_closed_early(self):
        with patch("app.services.csv_import.TemporaryFile", side_effect=self.capture_report_file):
            response = self.client.post(
                "/transactions/import",
                data={"file": (BytesIO(self.csv_bytes([
                    self.row(), self.row(amount="0"),
                ])), "transactions.csv")},
                content_type="multipart/form-data", buffered=False,
            )
        self.addCleanup(response.close)

        self.assertEqual(response.status_code, 200)
        prefix = next(response.response)
        self.assertIn(b'"errors":[', prefix)
        self.assertFalse(self.report_file.closed)

        response.close()

        self.assertTrue(self.report_file.closed)
        self.assertEqual(len(self.transactions()), 1)

    def test_report_file_closes_after_stream_is_fully_consumed(self):
        with patch("app.services.csv_import.TemporaryFile", side_effect=self.capture_report_file):
            response = self.upload(self.csv_bytes([self.row(amount="0")]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["failed"], 1)
        self.assertTrue(self.report_file.closed)

    def test_report_file_closes_when_preflight_rejects_file(self):
        for content in (b"wrong,header\n", self.csv_bytes([self.row()]) + b"\xff"):
            with self.subTest(content=content):
                with patch("app.services.csv_import.TemporaryFile", side_effect=self.capture_report_file):
                    response = self.upload(content)

                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertTrue(self.report_file.closed)
                self.assertEqual(self.transactions(), [])

    def test_report_file_closes_after_unexpected_database_error(self):
        with patch("app.services.csv_import.TemporaryFile", side_effect=self.capture_report_file):
            with patch.object(db.session, "execute", side_effect=SQLAlchemyError("private details")):
                response = self.upload(self.csv_bytes([self.row()]))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error"})
        self.assertTrue(self.report_file.closed)
        self.assertEqual(self.transactions(), [])

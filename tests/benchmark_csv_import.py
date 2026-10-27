"""Rucna provera milion redova: python -B -m tests.benchmark_csv_import."""

from decimal import Decimal
from tempfile import TemporaryFile
from time import perf_counter

from tests import BaseTestCase
from app import db
from app.models import Transaction


def main():
    # BaseTestCase koristi samo nasumicnu testnu PostgreSQL semu.
    case = BaseTestCase()
    case.setUp()
    try:
        category = case.client.post(
            "/categories", json={"name": "Hrana", "color": "#123456"}
        ).get_json()
        original = case.client.post("/transactions", json={
            "type": "income", "amount": "9.00", "date": "2026-09-01",
            "category_id": category["id"], "description": "Postojeca",
        }).get_json()

        with TemporaryFile() as upload:
            upload.write(b"type,amount,date,description,category\n")
            # Mesamo tipove, velika/mala slova i prazan/neprazan opis.
            block = (
                b"expense,12.50,2026-10-27,Rucak,Hrana\n"
                b"income,100.00,2026-10-28,,hRANA\n"
            ) * 500
            for _ in range(1000):
                upload.write(block)
            size = upload.tell()
            upload.seek(0)
            started = perf_counter()
            response = case.client.post(
                "/transactions/import", data={"file": (upload, "million.csv")},
                content_type="multipart/form-data", buffered=True,
            )
            try:
                case.assertEqual(response.status_code, 200, response.get_json())
                case.assertEqual(response.get_json(), {
                    "imported": 1_000_000, "failed": 0, "errors": [],
                })
            finally:
                response.close()
            elapsed = perf_counter() - started

        count, amount = db.session.execute(db.select(
            db.func.count(Transaction.id), db.func.sum(Transaction.amount),
        ).where(Transaction.id != original["id"])).one()
        case.assertEqual(count, 1_000_000)
        case.assertEqual(amount, Decimal("56250000.00"))
        case.assertEqual(
            case.client.get(f"/transactions/{original['id']}").get_json(), original
        )
        print(f"Imported {count:,} rows ({size:,} bytes) in {elapsed:.2f} seconds.", flush=True)
        print("Counts, exact decimal sum and existing transaction verified.", flush=True)
    finally:
        case.tearDown()


if __name__ == "__main__":
    main()

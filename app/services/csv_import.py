import csv
from dataclasses import dataclass
from io import TextIOWrapper
from tempfile import TemporaryFile

from loguru import logger
from pydantic import ValidationError
from sqlalchemy import String, column, func, insert, select, values
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest

from app.constants import (
    CSV_BATCH_SIZE,
    CSV_MAX_ROWS,
    CSV_OPTIONAL_COLUMNS,
    CSV_REQUIRED_COLUMNS,
    ConstraintName,
    ErrorMessage,
)
from app.extensions import db
from app.models import Category, Transaction
from app.schemas.common import validation_message
from app.schemas.csv_import import CsvImportCounts, CsvRowError, CsvTransactionInput


@dataclass
class ImportRow:
    number: int
    data: dict | None = None
    error: str | None = None


def _read_header(reader):
    header = [name.strip() for name in next(reader, [])]
    columns = set(header)
    if (
        len(columns) != len(header)
        or not CSV_REQUIRED_COLUMNS.issubset(columns)
        or columns - CSV_REQUIRED_COLUMNS - CSV_OPTIONAL_COLUMNS
    ):
        raise BadRequest(ErrorMessage.CSV_HEADER)
    return header


def _check_file(text):
    # Ceo fajl proveravamo pre upisa, ali ne cuvamo njegove redove u listi.
    reader = csv.reader(text, strict=True)
    _read_header(reader)
    for number, _ in enumerate(reader, start=1):
        if number > CSV_MAX_ROWS:
            raise BadRequest(ErrorMessage.CSV_ROW_LIMIT.format(limit=CSV_MAX_ROWS))
    text.seek(0)


def _parse_row(number, cells, header):
    if len(cells) != len(header):
        return ImportRow(number, error=ErrorMessage.CSV_COLUMNS)
    try:
        data = CsvTransactionInput.model_validate(dict(zip(header, cells)))
    except ValidationError as error:
        return ImportRow(number, error=validation_message(error))
    return ImportRow(number, data=data.model_dump())


def _resolve_categories(rows):
    names = {row.data["category"] for row in rows if row.data is not None}
    if not names:
        return
    # PostgreSQL lower na obe strane prati isto pravilo kao unique indeks.
    csv_names = values(column("name", String), name="csv_categories").data(
        [(name,) for name in names]
    )
    query = select(csv_names.c.name, Category.id).select_from(
        csv_names.join(Category, func.lower(csv_names.c.name) == func.lower(Category.name))
    )
    categories = dict(db.session.execute(query).all())
    for row in rows:
        if row.data is None:
            continue
        category_id = categories.get(row.data.pop("category"))
        if category_id is None:
            row.error = f"category: {ErrorMessage.CATEGORY_NOT_FOUND}"
        else:
            row.data["category_id"] = category_id


def _insert_rows(rows):
    statement = insert(Transaction.__table__)
    try:
        with db.session.begin_nested():
            db.session.execute(statement, [row.data for row in rows])
        return
    except IntegrityError as error:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint != ConstraintName.TRANSACTION_CATEGORY:
            raise

    # Ako je kategorija obrisana izmedju SELECT-a i INSERT-a, odbijamo samo te redove.
    for row in rows:
        try:
            with db.session.begin_nested():
                db.session.execute(statement, row.data)
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint != ConstraintName.TRANSACTION_CATEGORY:
                raise
            row.error = f"category: {ErrorMessage.CATEGORY_NOT_FOUND}"


def _process_batch(rows, counts, errors):
    _resolve_categories(rows)
    valid = [row for row in rows if row.error is None]
    if valid:
        _insert_rows(valid)
    for row in rows:
        if row.error is None:
            counts.imported += 1
        else:
            if counts.failed:
                errors.write(",")
            errors.write(CsvRowError(row=row.number, error=row.error).model_dump_json())
            counts.failed += 1


def import_transactions(stream):
    """Validira upload, upisuje pakete i vraca brojeve i privremeni izvestaj."""
    text = TextIOWrapper(stream, encoding="utf-8-sig", newline="")
    errors = TemporaryFile(mode="w+", encoding="utf-8", newline="")
    counts = CsvImportCounts()
    try:
        _check_file(text)
        reader = csv.reader(text, strict=True)
        header = _read_header(reader)
        batch = []
        for number, cells in enumerate(reader, start=2):
            batch.append(_parse_row(number, cells, header))
            if len(batch) == CSV_BATCH_SIZE:
                _process_batch(batch, counts, errors)
                batch.clear()
        if batch:
            _process_batch(batch, counts, errors)
        errors.seek(0)
        db.session.commit()
        logger.info("CSV import completed: imported={} failed={}", counts.imported, counts.failed)
        return counts, errors
    except (UnicodeError, csv.Error):
        errors.close()
        raise BadRequest(ErrorMessage.CSV_FORMAT) from None
    except BaseException:
        errors.close()
        raise
    finally:
        # FileStorage poseduje upload stream i zatvara ga na kraju zahteva.
        text.detach()


def stream_report(counts, errors):
    # Samo citanje gotovog izvestaja; sesija je vec zavrsena pre slanja odgovora.
    try:
        yield counts.model_dump_json()[:-1] + ',"errors":['
        while chunk := errors.read(64 * 1024):
            yield chunk
        yield "]}"
    finally:
        errors.close()

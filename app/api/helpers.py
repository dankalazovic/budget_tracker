from decimal import Decimal, InvalidOperation

from flask import current_app, request

from app.extensions import db


def is_category_name_conflict(error):
    if db.engine.dialect.name == "postgresql":
        return error.orig.diag.constraint_name == "uq_category_name_lower"

    # SQLite koristimo samo u testovima; on ime indeksa navodi u poruci.
    return str(error.orig) == "UNIQUE constraint failed: index 'uq_category_name_lower'"


def is_transaction_category_conflict(error):
    if db.engine.dialect.name == "postgresql":
        return error.orig.diag.constraint_name == "fk_transaction_category"
    return str(error.orig) == "FOREIGN KEY constraint failed"


def read_transaction_json():
    if not request.is_json:
        return None
    try:
        # Decimal cuva sve decimale koje je korisnik poslao, pre validacije.
        return current_app.json.loads(
            request.get_data(), parse_float=Decimal, parse_constant=Decimal
        )
    except (ValueError, InvalidOperation, RecursionError):
        return None



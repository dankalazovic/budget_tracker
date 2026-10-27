import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app import db
from app.models import Category


MAX_DATABASE_ID = 2147483647


def validate_amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Amount is required and must be a decimal number")

    if isinstance(value, str) and not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("Amount must be a valid decimal number")

    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("Amount must be a valid decimal number") from None

    if not amount.is_finite() or not Decimal("0") < amount <= Decimal("1000000"):
        raise ValueError("Amount must be greater than 0 and at most 1000000.00")

    if amount.as_tuple().exponent < -2:
        raise ValueError("Amount must have at most 2 decimal places")

    return amount


def validate_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Date is required and must be a valid date in YYYY-MM-DD format")

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Date is required and must be a valid date in YYYY-MM-DD format") from None


def validate_transaction(data, transaction=None):
    # Kod izmene izostavljena polja zadrzavaju postojece vrednosti.
    values = transaction.to_dict() if transaction is not None else {}
    values.update(data)

    transaction_type = values.get("type")
    if transaction_type not in ("income", "expense"):
        raise ValueError("Type is required and must be income or expense")

    amount = validate_amount(values.get("amount"))
    transaction_date = validate_date(values.get("date"))

    category_id = values.get("category_id")
    if type(category_id) is not int or not 1 <= category_id <= MAX_DATABASE_ID:
        raise ValueError("Category ID is required and must be a positive integer up to 2147483647")

    if db.session.get(Category, category_id) is None:
        raise ValueError("Category not found")

    description = values.get("description")
    if description is not None:
        if not isinstance(description, str) or len(description) > 200:
            raise ValueError("Description must be a string with at most 200 characters or null")
        if "\x00" in description:
            raise ValueError("Description contains invalid text characters")
        try:
            description.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Description contains invalid text characters") from None
        if description == "":
            description = None

    return {
        "type": transaction_type,
        "amount": amount,
        "date": transaction_date,
        "description": description,
        "category_id": category_id,
    }

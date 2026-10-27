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


def validate_query_integer(value, field, maximum=MAX_DATABASE_ID):
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"{field} must be an integer between 1 and {maximum}")

    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{field} must be an integer between 1 and {maximum}") from None

    if not 1 <= number <= maximum:
        raise ValueError(f"{field} must be an integer between 1 and {maximum}")
    return number


def validate_transaction_filters(args):
    fields = ("date_from", "date_to", "category_id", "type", "search", "page", "per_page")
    for field in fields:
        if len(args.getlist(field)) > 1:
            raise ValueError(f"{field} must be provided only once")

    dates = {"date_from": None, "date_to": None}
    for field in dates:
        if field in args:
            try:
                dates[field] = validate_date(args[field])
            except ValueError:
                raise ValueError(f"{field} must be a valid date in YYYY-MM-DD format") from None

    if dates["date_from"] is not None and dates["date_to"] is not None:
        if dates["date_from"] > dates["date_to"]:
            raise ValueError("date_from must be on or before date_to")

    category_id = None
    if "category_id" in args:
        category_id = validate_query_integer(args["category_id"], "category_id")

    transaction_type = args.get("type")
    if transaction_type is not None and transaction_type not in ("income", "expense"):
        raise ValueError("type must be income or expense")

    search = args.get("search")
    if search is not None:
        if "\x00" in search:
            raise ValueError("search contains invalid text characters")
        try:
            search.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("search contains invalid text characters") from None

    return {
        "date_from": dates["date_from"],
        "date_to": dates["date_to"],
        "category_id": category_id,
        "type": transaction_type,
        "search": search,
        "page": validate_query_integer(args.get("page", "1"), "page"),
        "per_page": validate_query_integer(args.get("per_page", "20"), "per_page", 100),
    }

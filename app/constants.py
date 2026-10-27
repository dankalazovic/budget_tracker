from enum import StrEnum


class ErrorMessage(StrEnum):
    CATEGORY_NOT_FOUND = "Category not found"
    TRANSACTION_NOT_FOUND = "Transaction not found"
    CATEGORY_EXISTS = "Category already exists"
    CATEGORY_HAS_TRANSACTIONS = "Category has transactions and cannot be deleted"
    INVALID_JSON = "Invalid JSON data"
    INTERNAL_SERVER_ERROR = "Internal server error"
    INVALID_TEXT = "Text contains invalid characters"
    INVALID_AMOUNT = "Amount must be a valid decimal number"
    AMOUNT_DECIMAL_PLACES = "Amount must have at most 2 decimal places"
    DATE_FORMAT = "Date must be in YYYY-MM-DD format"
    POSITIVE_INTEGER = "Value must be a positive integer"
    DATE_RANGE = "date_from must be on or before date_to"
    REPEATED_QUERY_PARAMETER = "{field} must be provided only once"


class ConstraintName(StrEnum):
    CATEGORY_NAME = "uq_category_name_lower"
    TRANSACTION_CATEGORY = "fk_transaction_category"


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

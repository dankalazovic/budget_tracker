from enum import StrEnum
from decimal import Decimal


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
    MONTH_FORMAT = "Month must be a valid month in YYYY-MM format"
    BUDGET_NOT_FOUND = "Budget not found"
    BUDGET_EXISTS = "Budget already exists for this category and month"
    CSV_FILE_REQUIRED = "Upload exactly one CSV file in the file field"
    CSV_HEADER = "CSV header must contain type, amount, date, category and optionally description"
    CSV_FORMAT = "File must be valid UTF-8 CSV with comma-separated columns"
    CSV_ROW_LIMIT = "CSV must contain at most {limit} data rows"
    CSV_COLUMNS = "Row must have the same number of columns as the header"


class ConstraintName(StrEnum):
    CATEGORY_NAME = "uq_category_name_lower"
    TRANSACTION_CATEGORY = "fk_transaction_category"
    BUDGET_CATEGORY = "fk_budget_category"
    BUDGET_CATEGORY_MONTH = "uq_budget_category_month"


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
ZERO_AMOUNT = Decimal("0.00")
CSV_MAX_ROWS = 1_000_000
CSV_BATCH_SIZE = 1_000
CSV_REQUIRED_COLUMNS = frozenset({"type", "amount", "date", "category"})
CSV_OPTIONAL_COLUMNS = frozenset({"description"})

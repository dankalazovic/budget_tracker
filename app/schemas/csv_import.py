from app.schemas.common import CategoryName, Schema
from app.schemas.transaction import TransactionFields


class CsvTransactionInput(TransactionFields):
    category: CategoryName


class CsvRowError(Schema):
    row: int
    error: str


class CsvImportCounts(Schema):
    imported: int = 0
    failed: int = 0

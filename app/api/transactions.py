from http import HTTPStatus

from flask import Blueprint, jsonify
from werkzeug.exceptions import BadRequest

from app.api.helpers import read_json_body, read_query, validate_input
from app.constants import ErrorMessage, MAX_PAGE_SIZE
from app.extensions import db
from app.models import Category, Transaction
from app.schemas import TransactionFilters, TransactionInput, TransactionListResponse, TransactionResponse


transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.route("/transactions", methods=["POST"])
def add_transaction():
    values = validate_input(TransactionInput, read_json_body())
    if db.session.get(Category, values.category_id) is None:
        raise BadRequest(ErrorMessage.CATEGORY_NOT_FOUND)

    transaction = Transaction(**values.model_dump())
    db.session.add(transaction)
    db.session.commit()
    return jsonify(TransactionResponse.model_validate(transaction).model_dump(mode="json")), HTTPStatus.CREATED


@transactions_bp.route("/transactions/<int:transaction_id>", methods=["GET"])
def get_transaction(transaction_id):
    transaction = db.get_or_404(Transaction, transaction_id, description=ErrorMessage.TRANSACTION_NOT_FOUND)
    return jsonify(TransactionResponse.model_validate(transaction).model_dump(mode="json")), HTTPStatus.OK


@transactions_bp.route("/transactions", methods=["GET"])
def get_transactions():
    filters = read_query(TransactionFilters)
    query = db.select(Transaction)
    if filters.date_from is not None:
        query = query.where(Transaction.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Transaction.date <= filters.date_to)
    if filters.category_id is not None:
        query = query.where(Transaction.category_id == filters.category_id)
    if filters.type is not None:
        query = query.where(Transaction.type == filters.type)
    if filters.search:
        query = query.where(Transaction.description.icontains(filters.search, autoescape=True))

    pagination = db.paginate(
        query.order_by(Transaction.date.desc(), Transaction.id.desc()),
        page=filters.page,
        per_page=filters.per_page,
        max_per_page=MAX_PAGE_SIZE,
        error_out=False,
    )
    response = TransactionListResponse(
        items=pagination.items,
        page=pagination.page,
        per_page=pagination.per_page,
        total=pagination.total,
        pages=pagination.pages,
    )
    return jsonify(response.model_dump(mode="json")), HTTPStatus.OK


@transactions_bp.route("/transactions/<int:transaction_id>", methods=["PUT"])
def update_transaction(transaction_id):
    transaction = db.get_or_404(Transaction, transaction_id, description=ErrorMessage.TRANSACTION_NOT_FOUND)
    data = TransactionResponse.model_validate(transaction).model_dump()
    data.update(read_json_body())
    values = validate_input(TransactionInput, data)
    if db.session.get(Category, values.category_id) is None:
        raise BadRequest(ErrorMessage.CATEGORY_NOT_FOUND)

    transaction.type = values.type
    transaction.amount = values.amount
    transaction.date = values.date
    transaction.description = values.description
    transaction.category_id = values.category_id
    db.session.commit()
    return jsonify(TransactionResponse.model_validate(transaction).model_dump(mode="json")), HTTPStatus.OK


@transactions_bp.route("/transactions/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    transaction = db.get_or_404(Transaction, transaction_id, description=ErrorMessage.TRANSACTION_NOT_FOUND)
    db.session.delete(transaction)
    db.session.commit()
    return "", HTTPStatus.NO_CONTENT

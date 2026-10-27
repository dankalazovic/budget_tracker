from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Transaction
from app.validation import MAX_DATABASE_ID, validate_transaction, validate_transaction_filters
from app.api.helpers import is_transaction_category_conflict, read_transaction_json


transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.route("/transactions", methods=["POST"])
def add_transaction():
    data = read_transaction_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data"}), 400

    try:
        values = validate_transaction(data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    transaction = Transaction(
        type=values["type"],
        amount=values["amount"],
        date=values["date"],
        description=values["description"],
        category_id=values["category_id"],
    )
    db.session.add(transaction)

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if is_transaction_category_conflict(error):
            return jsonify({"error": "Category not found"}), 400
        raise

    return jsonify(transaction.to_dict()), 201


@transactions_bp.route("/transactions/<int:transaction_id>", methods=["GET"])
def get_transaction(transaction_id):
    if not 1 <= transaction_id <= MAX_DATABASE_ID:
        return jsonify({"error": "Transaction not found"}), 404

    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "Transaction not found"}), 404

    return jsonify(transaction.to_dict()), 200


@transactions_bp.route("/transactions", methods=["GET"])
def get_transactions():
    try:
        filters = validate_transaction_filters(request.args)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    query = db.select(Transaction)

    if filters["date_from"] is not None:
        query = query.where(Transaction.date >= filters["date_from"])
    if filters["date_to"] is not None:
        query = query.where(Transaction.date <= filters["date_to"])
    if filters["category_id"] is not None:
        query = query.where(Transaction.category_id == filters["category_id"])
    if filters["type"] is not None:
        query = query.where(Transaction.type == filters["type"])
    if filters["search"]:
        # autoescape tretira % i _ kao tekst, a ne SQL wildcard znakove.
        query = query.where(
            Transaction.description.icontains(filters["search"], autoescape=True)
        )

    query = query.order_by(Transaction.date.desc(), Transaction.id.desc())
    pagination = db.paginate(
        query,
        page=filters["page"],
        per_page=filters["per_page"],
        max_per_page=100,
        error_out=False,
    )

    return jsonify({
        "items": [transaction.to_dict() for transaction in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }), 200


@transactions_bp.route("/transactions/<int:transaction_id>", methods=["PUT"])
def update_transaction(transaction_id):
    if not 1 <= transaction_id <= MAX_DATABASE_ID:
        return jsonify({"error": "Transaction not found"}), 404

    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "Transaction not found"}), 404

    data = read_transaction_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data"}), 400

    try:
        values = validate_transaction(data, transaction)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    transaction.type = values["type"]
    transaction.amount = values["amount"]
    transaction.date = values["date"]
    transaction.description = values["description"]
    transaction.category_id = values["category_id"]

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if is_transaction_category_conflict(error):
            return jsonify({"error": "Category not found"}), 400
        raise

    return jsonify(transaction.to_dict()), 200


@transactions_bp.route("/transactions/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    if not 1 <= transaction_id <= MAX_DATABASE_ID:
        return jsonify({"error": "Transaction not found"}), 404

    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "Transaction not found"}), 404

    db.session.delete(transaction)
    db.session.commit()
    return "", 204

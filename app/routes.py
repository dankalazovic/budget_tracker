import re
from decimal import Decimal, InvalidOperation

from flask import request, jsonify
from sqlalchemy.exc import IntegrityError
from app import app, db
from app.models import Category, Transaction
from app.validation import MAX_DATABASE_ID, validate_transaction


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
        return app.json.loads(
            request.get_data(), parse_float=Decimal, parse_constant=Decimal
        )
    except (ValueError, InvalidOperation, RecursionError):
        return None


@app.route("/")
def home():
    return {"message": "Budget Tracker API is running"}


@app.route("/categories", methods=["POST"])
def add_category():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data"}), 400

    name = data.get("name")
    color = data.get("color")

    if not isinstance(name, str):
        return jsonify({"error": "Category name is required"}), 400

    name = name.strip()

    if not 1 <= len(name) <= 30:
        return jsonify({"error": "Name must have 1 to 30 characters"}), 400

    if "\x00" in name:
        return jsonify({"error": "Name contains invalid text characters"}), 400

    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return jsonify({"error": "Name contains invalid text characters"}), 400

    if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return jsonify({"error": "Color must be in #RRGGBB format"}), 400

    existing_category = db.session.execute(
        db.select(Category).where(
            db.func.lower(Category.name) == db.func.lower(name)
        )
    ).scalar_one_or_none()

    if existing_category:
        return jsonify({"error": "Category already exists"}), 409

    category = Category(name=name, color=color)

    db.session.add(category)

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if is_category_name_conflict(error):
            return jsonify({"error": "Category already exists"}), 409
        raise

    return jsonify({
        "id": category.id,
        "name": category.name,
        "color": category.color
    }), 201


@app.route("/categories", methods=["GET"])
def get_categories():
    categories = db.session.execute(
        db.select(Category).order_by(Category.name)
    ).scalars().all()

    result = []

    for category in categories:
        result.append({
            "id": category.id,
            "name": category.name,
            "color": category.color
        })

    return jsonify(result), 200


@app.route("/categories/<int:category_id>", methods=["PUT"])
def update_category(category_id):
    if not 1 <= category_id <= MAX_DATABASE_ID:
        return jsonify({"error": "Category not found"}), 404

    category = db.session.get(Category, category_id)

    if category is None:
        return jsonify({"error": "Category not found"}), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data"}), 400

    name = data.get("name", category.name)
    color = data.get("color", category.color)

    if not isinstance(name, str):
        return jsonify({"error": "Invalid category name"}), 400

    name = name.strip()

    if not 1 <= len(name) <= 30:
        return jsonify({"error": "Name must have 1 to 30 characters"}), 400

    if "\x00" in name:
        return jsonify({"error": "Name contains invalid text characters"}), 400

    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return jsonify({"error": "Name contains invalid text characters"}), 400

    if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return jsonify({"error": "Color must be in #RRGGBB format"}), 400

    existing_category = db.session.execute(
        db.select(Category).where(
            db.func.lower(Category.name) == db.func.lower(name),
            Category.id != category_id
        )
    ).scalar_one_or_none()

    if existing_category:
        return jsonify({"error": "Category already exists"}), 409

    category.name = name
    category.color = color

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if is_category_name_conflict(error):
            return jsonify({"error": "Category already exists"}), 409
        raise

    return jsonify({
        "id": category.id,
        "name": category.name,
        "color": category.color
    }), 200


@app.route("/categories/<int:category_id>", methods=["DELETE"])
def delete_category(category_id):
    if not 1 <= category_id <= MAX_DATABASE_ID:
        return jsonify({"error": "Category not found"}), 404

    category = db.session.get(Category, category_id)

    if category is None:
        return jsonify({"error": "Category not found"}), 404

    transaction_id = db.session.execute(
        db.select(Transaction.id).where(Transaction.category_id == category_id).limit(1)
    ).scalar_one_or_none()

    if transaction_id is not None:
        return jsonify({"error": "Category has transactions and cannot be deleted"}), 409

    db.session.delete(category)

    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if is_transaction_category_conflict(error):
            return jsonify({"error": "Category has transactions and cannot be deleted"}), 409
        raise

    return "", 204


@app.route("/transactions", methods=["POST"])
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


@app.route("/transactions/<int:transaction_id>", methods=["GET"])
def get_transaction(transaction_id):
    if not 1 <= transaction_id <= MAX_DATABASE_ID:
        return jsonify({"error": "Transaction not found"}), 404

    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "Transaction not found"}), 404

    return jsonify(transaction.to_dict()), 200


@app.route("/transactions/<int:transaction_id>", methods=["PUT"])
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


@app.route("/transactions/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    if not 1 <= transaction_id <= MAX_DATABASE_ID:
        return jsonify({"error": "Transaction not found"}), 404

    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "Transaction not found"}), 404

    db.session.delete(transaction)
    db.session.commit()
    return "", 204

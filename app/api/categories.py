import re

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Category, Transaction
from app.validation import MAX_DATABASE_ID
from app.api.helpers import is_category_name_conflict, is_transaction_category_conflict


categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/categories", methods=["POST"])
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


@categories_bp.route("/categories", methods=["GET"])
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


@categories_bp.route("/categories/<int:category_id>", methods=["PUT"])
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


@categories_bp.route("/categories/<int:category_id>", methods=["DELETE"])
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



from http import HTTPStatus

from flask import Blueprint, jsonify
from werkzeug.exceptions import Conflict

from app.api.helpers import read_json_body, validate_input
from app.constants import ErrorMessage
from app.extensions import db
from app.models import Category, Transaction
from app.schemas import CategoryCreate, CategoryResponse


categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/categories", methods=["POST"])
def add_category():
    values = validate_input(CategoryCreate, read_json_body())
    existing = db.session.execute(
        db.select(Category).where(db.func.lower(Category.name) == db.func.lower(values.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict(ErrorMessage.CATEGORY_EXISTS)

    category = Category(**values.model_dump())
    db.session.add(category)
    db.session.commit()
    return jsonify(CategoryResponse.model_validate(category).model_dump(mode="json")), HTTPStatus.CREATED


@categories_bp.route("/categories", methods=["GET"])
def get_categories():
    categories = db.session.execute(
        db.select(Category).order_by(Category.name)
    ).scalars().all()
    result = [CategoryResponse.model_validate(category).model_dump(mode="json") for category in categories]
    return jsonify(result), HTTPStatus.OK


@categories_bp.route("/categories/<int:category_id>", methods=["PUT"])
def update_category(category_id):
    category = db.get_or_404(Category, category_id, description=ErrorMessage.CATEGORY_NOT_FOUND)
    data = CategoryResponse.model_validate(category).model_dump()
    data.update(read_json_body())
    values = validate_input(CategoryCreate, data)
    existing = db.session.execute(
        db.select(Category).where(
            db.func.lower(Category.name) == db.func.lower(values.name),
            Category.id != category_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict(ErrorMessage.CATEGORY_EXISTS)

    category.name = values.name
    category.color = values.color
    db.session.commit()
    return jsonify(CategoryResponse.model_validate(category).model_dump(mode="json")), HTTPStatus.OK


@categories_bp.route("/categories/<int:category_id>", methods=["DELETE"])
def delete_category(category_id):
    db.get_or_404(Category, category_id, description=ErrorMessage.CATEGORY_NOT_FOUND)
    transaction_id = db.session.execute(
        db.select(Transaction.id).where(Transaction.category_id == category_id).limit(1)
    ).scalar_one_or_none()
    if transaction_id is not None:
        raise Conflict(ErrorMessage.CATEGORY_HAS_TRANSACTIONS)

    # Direktan DELETE prepusta RESTRICT/CASCADE pravilima baze povezane redove.
    db.session.execute(db.delete(Category).where(Category.id == category_id))
    db.session.commit()
    return "", HTTPStatus.NO_CONTENT

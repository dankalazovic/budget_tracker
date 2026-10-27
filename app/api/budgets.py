from http import HTTPStatus

from flask import Blueprint, jsonify
from werkzeug.exceptions import NotFound

from app.api.helpers import read_json_body, read_query, validate_input
from app.constants import ErrorMessage
from app.extensions import db
from app.models import Budget, Category
from app.schemas import BudgetInput, BudgetMonth, BudgetResponse


budgets_bp = Blueprint("budgets", __name__)


@budgets_bp.route("/budgets/<month>/<int:category_id>", methods=["PUT"])
def set_budget(month, category_id):
    month = validate_input(BudgetMonth, {"month": month}).month
    db.get_or_404(Category, category_id, description=ErrorMessage.CATEGORY_NOT_FOUND)
    values = validate_input(BudgetInput, read_json_body())
    budget = db.session.execute(
        db.select(Budget).where(Budget.month == month, Budget.category_id == category_id)
    ).scalar_one_or_none()

    status = HTTPStatus.OK
    if budget is None:
        budget = Budget(month=month, category_id=category_id, amount=values.amount)
        db.session.add(budget)
        status = HTTPStatus.CREATED
    else:
        budget.amount = values.amount

    db.session.commit()
    return jsonify(BudgetResponse.model_validate(budget).model_dump(mode="json")), status


@budgets_bp.route("/budgets", methods=["GET"])
def get_budgets():
    month = read_query(BudgetMonth).month
    budgets = db.session.execute(
        db.select(Budget).join(Category).where(Budget.month == month)
        .order_by(Category.name.asc(), Budget.id.asc())
    ).scalars().all()
    result = [BudgetResponse.model_validate(budget).model_dump(mode="json") for budget in budgets]
    return jsonify(result), HTTPStatus.OK


@budgets_bp.route("/budgets/<month>/<int:category_id>", methods=["DELETE"])
def delete_budget(month, category_id):
    month = validate_input(BudgetMonth, {"month": month}).month
    budget = db.session.execute(
        db.select(Budget).where(Budget.month == month, Budget.category_id == category_id)
    ).scalar_one_or_none()
    if budget is None:
        raise NotFound(ErrorMessage.BUDGET_NOT_FOUND)

    db.session.delete(budget)
    db.session.commit()
    return "", HTTPStatus.NO_CONTENT

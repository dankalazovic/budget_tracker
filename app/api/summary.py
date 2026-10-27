from calendar import monthrange
from http import HTTPStatus

from flask import Blueprint, jsonify
from sqlalchemy import func

from app.api.helpers import read_query
from app.constants import ZERO_AMOUNT
from app.extensions import db
from app.models import Budget, Category, Transaction
from app.schemas.summary import CategorySummary, MonthlySummaryResponse, SummaryQuery
from app.schemas.transaction import TransactionType


summary_bp = Blueprint("summary", __name__)


@summary_bp.route("/summary", methods=["GET"])
def monthly_summary():
    month = read_query(SummaryQuery).month
    last_day = month.replace(day=monthrange(month.year, month.month)[1])
    in_month = Transaction.date.between(month, last_day)

    # Baza sabira iznose; ne ucitavamo sve transakcije u Python.
    totals = dict(db.session.execute(
        db.select(Transaction.type, func.sum(Transaction.amount))
        .where(in_month).group_by(Transaction.type)
    ).all())
    total_income = totals.get(TransactionType.INCOME.value, ZERO_AMOUNT)
    total_expense = totals.get(TransactionType.EXPENSE.value, ZERO_AMOUNT)

    spent_by_category = dict(db.session.execute(
        db.select(Transaction.category_id, func.sum(Transaction.amount))
        .where(in_month, Transaction.type == TransactionType.EXPENSE.value)
        .group_by(Transaction.category_id)
    ).all())
    budgets_by_category = dict(db.session.execute(
        db.select(Budget.category_id, Budget.amount).where(Budget.month == month)
    ).all())

    category_ids = set(spent_by_category) | set(budgets_by_category)
    categories = []
    if category_ids:
        records = db.session.execute(
            db.select(Category).where(Category.id.in_(category_ids))
        ).scalars().all()
        for category in records:
            spent = spent_by_category.get(category.id, ZERO_AMOUNT)
            budget = budgets_by_category.get(category.id, ZERO_AMOUNT)
            categories.append(CategorySummary(
                category_id=category.id,
                category_name=category.name,
                spent=spent,
                budget=budget,
                remaining=budget - spent,
            ))

    categories.sort(key=lambda item: (-item.spent, item.category_name, item.category_id))
    response = MonthlySummaryResponse(
        month=month,
        total_income=total_income,
        total_expense=total_expense,
        balance=total_income - total_expense,
        categories=categories,
    )
    return jsonify(response.model_dump(mode="json")), HTTPStatus.OK

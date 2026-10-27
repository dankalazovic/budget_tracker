from app.api.categories import categories_bp
from app.api.csv_import import csv_import_bp
from app.api.budgets import budgets_bp
from app.api.health import health_bp
from app.api.transactions import transactions_bp
from app.api.summary import summary_bp


def register_blueprints(app):
    app.register_blueprint(budgets_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(csv_import_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(summary_bp)

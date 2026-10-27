from app.api.categories import categories_bp
from app.api.health import health_bp
from app.api.transactions import transactions_bp


def register_blueprints(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(transactions_bp)

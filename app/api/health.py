from flask import Blueprint


health_bp = Blueprint("health", __name__)


@health_bp.route("/")
def home():
    return {"message": "Budget Tracker API is running"}



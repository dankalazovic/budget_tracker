from flask import request
from loguru import logger

from app.errors import request_route
from app.extensions import db


def register_session_lifecycle(app):
    @app.before_request
    def start_session():
        # Sesija pripada trenutnom zahtevu; konekciju uzima tek pri prvom upitu.
        db.session()

    @app.after_request
    def log_response(response):
        logger.info(
            "Request completed: method={} route={} status={}",
            request.method, request_route(), response.status_code,
        )
        return response

    @app.teardown_request
    def close_session(error=None):
        try:
            # Potvrdjen commit ostaje sacuvan; preostali rad se ponistava.
            db.session.rollback()
        finally:
            db.session.remove()

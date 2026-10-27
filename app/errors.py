from http import HTTPStatus

from flask import current_app, jsonify, request
from loguru import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.constants import ConstraintName, ErrorMessage


INTEGRITY_ERRORS = {
    (ConstraintName.BUDGET_CATEGORY_MONTH, None): (
        HTTPStatus.CONFLICT, ErrorMessage.BUDGET_EXISTS,
    ),
    (ConstraintName.BUDGET_CATEGORY, None): (
        HTTPStatus.NOT_FOUND, ErrorMessage.CATEGORY_NOT_FOUND,
    ),
    (ConstraintName.CATEGORY_NAME, None): (
        HTTPStatus.CONFLICT, ErrorMessage.CATEGORY_EXISTS,
    ),
    (ConstraintName.TRANSACTION_CATEGORY, "categories.delete_category"): (
        HTTPStatus.CONFLICT, ErrorMessage.CATEGORY_HAS_TRANSACTIONS,
    ),
    (ConstraintName.TRANSACTION_CATEGORY, None): (
        HTTPStatus.BAD_REQUEST, ErrorMessage.CATEGORY_NOT_FOUND,
    ),
}


def request_route():
    return request.url_rule.rule if request.url_rule is not None else "<unmatched>"


def server_error(error):
    # Ne logujemo exception tekst: DB greske mogu sadrzati SQL i podatke unosa.
    logger.error(
        "Request failed: method={} route={} error={}",
        request.method, request_route(), type(error).__name__,
    )
    return jsonify({"error": ErrorMessage.INTERNAL_SERVER_ERROR}), HTTPStatus.INTERNAL_SERVER_ERROR


def http_error(error):
    status = error.code or HTTPStatus.INTERNAL_SERVER_ERROR
    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        message = ErrorMessage.INTERNAL_SERVER_ERROR
        logger.error(
            "Request failed: method={} route={} error={}",
            request.method, request_route(), type(error).__name__,
        )
    else:
        message = error.description
        logger.warning(
            "Request rejected: method={} route={} status={}",
            request.method, request_route(), status,
        )

    # Zadrzavamo HTTP zaglavlja, na primer Allow za odgovor 405.
    response = error.get_response()
    response.set_data(current_app.json.dumps({"error": message}))
    response.content_type = "application/json"
    response.status_code = status
    return response


def integrity_error(error):
    diagnostic = getattr(error.orig, "diag", None)
    constraint = getattr(diagnostic, "constraint_name", None)
    result = INTEGRITY_ERRORS.get((constraint, request.endpoint))
    if result is None:
        result = INTEGRITY_ERRORS.get((constraint, None))
    if result is None:
        return server_error(error)

    status, message = result
    logger.warning(
        "Database rule rejected request: method={} route={} status={}",
        request.method, request_route(), status.value,
    )
    return jsonify({"error": message}), status


def register_error_handlers(app):
    app.register_error_handler(HTTPException, http_error)
    app.register_error_handler(IntegrityError, integrity_error)
    app.register_error_handler(SQLAlchemyError, server_error)
    app.register_error_handler(Exception, server_error)

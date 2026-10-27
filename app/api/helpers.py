from decimal import Decimal, InvalidOperation

from flask import current_app, request
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest

from app.constants import ErrorMessage


def read_json_body():
    if not request.is_json:
        raise BadRequest(ErrorMessage.INVALID_JSON)
    try:
        # Decimal cuva sve decimale koje je korisnik poslao, pre validacije.
        data = current_app.json.loads(
            request.get_data(), parse_float=Decimal, parse_constant=Decimal
        )
    except (ValueError, InvalidOperation, RecursionError):
        raise BadRequest(ErrorMessage.INVALID_JSON) from None
    if not isinstance(data, dict):
        raise BadRequest(ErrorMessage.INVALID_JSON)
    return data


def read_query(schema):
    for field in schema.model_fields:
        if len(request.args.getlist(field)) > 1:
            raise BadRequest(ErrorMessage.REPEATED_QUERY_PARAMETER.format(field=field))
    return validate_input(schema, request.args.to_dict())


def validate_input(schema, data):
    try:
        return schema.model_validate(data)
    except ValidationError as error:
        first = error.errors(include_input=False, include_context=False, include_url=False)[0]
        field = ".".join(str(part) for part in first["loc"])
        message = f"{field}: {first['msg']}" if field else first["msg"]
        raise BadRequest(message) from None



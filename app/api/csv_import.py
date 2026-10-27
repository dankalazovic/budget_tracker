from flask import Blueprint, Response, request
from werkzeug.exceptions import BadRequest

from app.constants import ErrorMessage
from app.services.csv_import import import_transactions, stream_report


csv_import_bp = Blueprint("csv_import", __name__)


@csv_import_bp.post("/transactions/import")
def upload_transactions():
    uploads = list(request.files.items(multi=True))
    if len(uploads) != 1 or uploads[0][0] != "file" or not uploads[0][1].filename:
        raise BadRequest(ErrorMessage.CSV_FILE_REQUIRED)
    counts, errors = import_transactions(uploads[0][1].stream)
    response = Response(stream_report(counts, errors), mimetype="application/json")
    response.call_on_close(errors.close)
    return response

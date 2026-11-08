from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Format error konsisten, sesuai docs/api-guide.md."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        code, message, details = "VALIDATION_ERROR", "The request could not be validated.", response.data
    else:
        code = getattr(exc, "default_code", "error").upper()
        message = str(getattr(exc, "detail", "Request failed."))
        details = None
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
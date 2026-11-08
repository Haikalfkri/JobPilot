from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class InvalidWorkflow(APIException):
    """The request is well-formed but not allowed in the current state (HTTP 422)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This action is not allowed in the current state."
    default_code = "invalid_workflow"


def api_exception_handler(exc, context):
    """Consistent error envelope, as described in docs/api-guide.md."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        code, message, details = "VALIDATION_ERROR", "The request could not be validated.", response.data
    elif isinstance(exc, Http404):
        code, message, details = "NOT_FOUND", "Resource not found.", None
    else:
        code = getattr(exc, "default_code", "error").upper()
        message = str(getattr(exc, "detail", "Request failed."))
        details = None
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
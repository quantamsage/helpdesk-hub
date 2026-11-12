"""One error format for every response: {"error": {"code", "message"}}.

Clients only ever see safe, generic messages. Full details of unexpected
errors are logged on the server (see main.py).
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

GENERIC_SERVER_ERROR = "Something went wrong on our side. Please try again."


class ApiError(Exception):
    """Raise this from any route to return a clean JSON error."""

    def __init__(self, status_code: int, code: str, message: str, details: list | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_body(code: str, message: str, details: list | None = None) -> dict:
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def not_found() -> ApiError:
    # Same message whether the ticket doesn't exist or belongs to someone else.
    return ApiError(404, "not_found", "Ticket not found.")


def field_error(field: str, message: str) -> ApiError:
    return ApiError(422, "validation_error", "Some fields are invalid.", [{"field": field, "message": message}])


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)


async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details))


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [_describe(err) for err in exc.errors()]
    return JSONResponse(status_code=422, content=error_body("validation_error", "Some fields are invalid.", details))


def _describe(err: dict) -> dict:
    """Turn a Pydantic error into {"field", "message"}. The submitted value
    is never echoed back (it could be a password)."""
    if err.get("type") == "json_invalid":
        return {"field": "body", "message": "Request body is not valid JSON."}
    parts = [str(p) for p in err["loc"] if p not in ("body", "query", "path", "header")]
    message = err["msg"].removeprefix("Value error, ")
    return {"field": ".".join(parts) or "body", "message": message}


_HTTP_CODES = {
    401: ("unauthorized", "Please log in."),
    403: ("forbidden", "You don't have permission to do this."),
    404: ("not_found", "Not found."),
    405: ("method_not_allowed", "This endpoint doesn't support that method."),
}


async def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Framework errors, e.g. a URL that doesn't exist."""
    code, message = _HTTP_CODES.get(exc.status_code, ("internal_error", GENERIC_SERVER_ERROR))
    return JSONResponse(status_code=exc.status_code, content=error_body(code, message), headers=getattr(exc, "headers", None))

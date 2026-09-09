from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import APIError


def _field_from_loc(loc) -> str | None:
    parts = [
        str(part)
        for part in loc
        if part not in ("body", "query", "path", "header", "cookie")
    ]
    return ".".join(parts) or None


def _friendly_message(err: dict) -> str:
    err_type = err.get("type", "")
    ctx = err.get("ctx") or {}
    msg = err.get("msg", "")

    if err_type in ("missing", "required"):
        return "This field is required."
    if err_type in ("string_too_short", "too_short"):
        min_len = ctx.get("min_length")
        return f"Must be at least {min_len} characters." if min_len else "Value is too short."
    if err_type in ("string_too_long", "too_long"):
        max_len = ctx.get("max_length")
        return f"Must be at most {max_len} characters." if max_len else "Value is too long."
    if err_type in ("string_type", "bytes_type"):
        return "Expected a string."
    if err_type in ("int_type", "number_type", "float_type", "decimal_type"):
        return "Expected a number."
    if err_type == "bool_type":
        return "Expected true or false."
    if err_type == "uuid_type":
        return "Expected a valid UUID."
    if err_type in ("date_type", "datetime_type", "time_type"):
        return "Expected a valid date/time."
    if err_type == "email_type" or "email" in msg.lower():
        return "Enter a valid email address."

    # Custom validators (e.g. password rules) and everything else.
    cleaned = msg
    for prefix in ("Value error, ", "Input should be "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]

    ctx_error = ctx.get("error")
    if isinstance(ctx_error, Exception) and str(ctx_error):
        cleaned = str(ctx_error).strip()
        if cleaned.startswith("Value error, "):
            cleaned = cleaned[len("Value error, "):]

    cleaned = cleaned.strip()
    if cleaned:
        return cleaned[0].upper() + cleaned[1:]
    return "Invalid value."


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": _field_from_loc(err.get("loc", ())),
            "message": _friendly_message(err),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422, content={"detail": "Validation failed", "errors": errors}
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(APIError, api_error_handler)

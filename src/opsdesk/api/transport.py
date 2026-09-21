import json

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

from opsdesk.api.errors import error_response

VALIDATION_MESSAGES = {
    "missing": "Field is required.",
    "extra_forbidden": "Unexpected field.",
}

HTTP_ERROR_CODES = {
    401: "unauthenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    415: "unsupported_media_type",
    422: "validation_error",
}


class JsonAPIRoute(APIRoute):
    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            if self.body_field is not None:
                body = await request.body()

                if body:
                    content_types = request.headers.getlist("content-type")
                    if len(content_types) != 1:
                        return error_response("unsupported_media_type")

                    media_type = content_types[0].split(";", 1)[0].strip().lower()
                    if media_type != "application/json":
                        return error_response("unsupported_media_type")

                    try:
                        await request.json()
                    except json.JSONDecodeError, UnicodeDecodeError:
                        return error_response("invalid_json")

            return await original_handler(request)

        return handler


def safe_validation_field(request: Request, location: tuple) -> str:
    if not location or location[0] not in {"body", "query", "path"}:
        return "request"

    source = location[0]
    if len(location) < 2:
        return source

    route = request.scope.get("route")
    if not isinstance(route, APIRoute):
        return source

    known_fields = set()

    if source == "body":
        body_field = route.body_field
        annotation = (
            body_field.field_info.annotation if body_field is not None else None
        )
        model_fields = getattr(annotation, "model_fields", {})

        for name, field in model_fields.items():
            known_fields.add(field.alias or name)
    else:
        parameters = getattr(route.dependant, f"{source}_params", [])
        for parameter in parameters:
            known_fields.add(parameter.alias)

    field_name = location[1]
    if isinstance(field_name, str) and field_name in known_fields:
        return f"{source}.{field_name}"

    return source


async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()

    if any(error.get("type") == "json_invalid" for error in errors):
        return error_response("invalid_json")

    details = [
        {
            "field": safe_validation_field(
                request,
                tuple(error.get("loc", ())),
            ),
            "message": VALIDATION_MESSAGES.get(
                error.get("type"),
                "Invalid value.",
            ),
        }
        for error in errors[:20]
    ]

    return error_response("validation_error", details=details)


async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    code = HTTP_ERROR_CODES.get(exc.status_code)

    if code is not None:
        response = error_response(code)
    elif 400 <= exc.status_code < 500:
        response = JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": "Request could not be processed.",
                    "details": [],
                }
            },
        )
    else:
        response = error_response("internal_error")

    if exc.status_code == 405:
        for name, value in (exc.headers or {}).items():
            if name.lower() == "allow":
                response.headers["Allow"] = value

    return response


def install_transport_handlers(app: FastAPI) -> None:
    app.router.route_class = JsonAPIRoute
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_error)

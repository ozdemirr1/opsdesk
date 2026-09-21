from fastapi import Request
from fastapi.responses import JSONResponse

ERROR_DEFINITIONS: dict[str, tuple[int, str]] = {
    "unauthenticated": (401, "Authentication required."),
    "organization_access_denied": (403, "Organization access denied."),
    "ticket_not_found": (404, "Ticket not found."),
    "permission_denied": (403, "Permission denied."),
    "organization_suspended": (403, "Organization is suspended."),
    "validation_error": (422, "Request validation failed."),
    "state_conflict": (409, "Operation conflicts with the current state."),
    "membership_exists": (409, "Membership already exists."),
    "user_not_addable": (400, "User cannot be added."),
    "email_already_exists": (409, "Email already exists."),
    "invalid_json": (400, "Request body is not valid JSON."),
    "unsupported_media_type": (415, "Content-Type must be application/json."),
    "internal_error": (500, "An unexpected error occurred."),
    "not_found": (404, "Resource not found."),
    "method_not_allowed": (405, "Method not allowed."),
}


class ApiError(Exception):
    def __init__(self, code: str) -> None:
        if code not in ERROR_DEFINITIONS:
            raise ValueError("Unknown API error code.")

        self.code = code
        super().__init__(code)


def error_response(
    code: str,
    *,
    details: list[dict[str, str]] | None = None,
) -> JSONResponse:
    status_code, message = ERROR_DEFINITIONS[code]
    headers = {"WWW-Authenticate": "Bearer"} if code == "unauthenticated" else None

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details if details is not None else [],
            }
        },
        headers=headers,
    )


async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.code)

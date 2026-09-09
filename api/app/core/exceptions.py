class APIError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class ConflictError(APIError):
    status_code = 409


class UnauthorizedError(APIError):
    status_code = 401


class NotFoundError(APIError):
    status_code = 404

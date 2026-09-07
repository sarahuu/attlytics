from pydantic import BaseModel

from app import __version__


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = __version__
    checks: dict[str, str]

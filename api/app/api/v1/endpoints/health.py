from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.db.session import get_db
from app.schemas.health import HealthResponse
from app.services.health import build_health_report

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and readiness probe",
)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    report = build_health_report(db, version=__version__)
    return HealthResponse(**report)

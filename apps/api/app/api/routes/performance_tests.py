import uuid
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.performance_tests import (
    PerformanceTestCreate,
)
from app.services.performance_test_service import (
    PerformanceTestService,
)
from app.services.performance_test_analysis_service import (
    PerformanceTestAnalysisService,
)


router = APIRouter(
    prefix="/v1/performance-tests",
    tags=["performance-tests"],
)


def _handle_error(
    exc: Exception,
):
    if isinstance(
        exc,
        LookupError,
    ):
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=400,
        detail=str(exc),
    ) from exc


@router.post(
    "",
    status_code=201,
)
def create_performance_test(
    payload: PerformanceTestCreate,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceTestService(
            db
        ).create(payload)

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("")
def list_performance_tests(
    athlete_id: uuid.UUID,
    test_type: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        return {
            "items":
                PerformanceTestService(
                    db
                ).list(
                    athlete_id=athlete_id,
                    test_type=test_type,
                )
        }

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("/source-comparison")
def compare_power_sources(
    athlete_id: uuid.UUID,
    source_a_id: uuid.UUID,
    source_b_id: uuid.UUID,
    environment: str | None = None,
    discipline: str | None = None,
    protocol: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceTestAnalysisService(
            db
        ).compare_sources(
            athlete_id=athlete_id,
            source_a_id=source_a_id,
            source_b_id=source_b_id,
            environment=environment,
            discipline=discipline,
            protocol=protocol,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("/ftp-proposal")
def get_ftp_proposal(
    athlete_id: uuid.UUID,
    power_source_id: uuid.UUID,
    environment: str,
    discipline: str | None = None,
    at: datetime | None = None,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceTestAnalysisService(
            db
        ).ftp_proposal(
            athlete_id=athlete_id,
            power_source_id=
                power_source_id,
            environment=environment,
            discipline=discipline,
            at=at,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("/{test_id}")
def get_performance_test(
    test_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceTestService(
            db
        ).get(
            athlete_id=athlete_id,
            test_id=test_id,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)

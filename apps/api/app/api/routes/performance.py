import uuid
from datetime import datetime
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.performance import ZoneSetCreate
from app.services.performance_profile_service import (
    PerformanceProfileService,
)


router = APIRouter(
    prefix="/v1/performance",
    tags=["performance"],
)


PerformanceEnvironment = Literal[
    "indoor",
    "outdoor",
]


def _handle_error(exc: Exception):
    if isinstance(exc, LookupError):
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=400,
        detail=str(exc),
    ) from exc


@router.post(
    "/zone-sets",
    status_code=201,
)
def create_zone_set(
    payload: ZoneSetCreate,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceProfileService(
            db
        ).create_zone_set(payload)

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("/zone-sets")
def list_zone_sets(
    athlete_id: uuid.UUID,
    sport: str = "cycling",
    context: PerformanceEnvironment | None = None,
    environment:
        PerformanceEnvironment | None = None,
    discipline: str | None = None,
    power_source_id:
        uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    try:
        return {
            "items":
                PerformanceProfileService(
                    db
                ).list_zone_sets(
                    athlete_id=athlete_id,
                    sport=sport,
                    context=context,
                    environment=environment,
                    discipline=discipline,
                    power_source_id=
                        power_source_id,
                )
        }

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("/effective-zone-set")
def get_effective_zone_set(
    athlete_id: uuid.UUID,
    at: datetime,
    sport: str = "cycling",
    context: PerformanceEnvironment | None = None,
    environment:
        PerformanceEnvironment | None = None,
    discipline: str | None = None,
    power_source_id:
        uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    try:
        item = PerformanceProfileService(
            db
        ).effective_zone_set(
            athlete_id=athlete_id,
            sport=sport,
            context=context,
            environment=environment,
            discipline=discipline,
            power_source_id=
                power_source_id,
            at=at,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No effective zone set "
                "for this date and profile"
            ),
        )

    return item

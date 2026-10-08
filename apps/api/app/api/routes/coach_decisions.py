import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.coach_decision_service import (
    CoachDecisionService,
)


router = APIRouter(
    prefix="/v1/coach-decisions",
    tags=["coach-decisions"],
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
    "/weekly/{week_id}/evaluate"
)
def evaluate_weekly_decision(
    week_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return CoachDecisionService(
            db
        ).evaluate(
            athlete_id=athlete_id,
            week_id=week_id,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get(
    "/weekly/{week_id}"
)
def get_latest_weekly_decision(
    week_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        result = CoachDecisionService(
            db
        ).latest(
            athlete_id=athlete_id,
            week_id=week_id,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Coach decision "
                    "not generated"
                ),
            )

        return result

    except HTTPException:
        raise

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get(
    "/weekly/{week_id}/history"
)
def get_weekly_decision_history(
    week_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return {
            "items":
                CoachDecisionService(
                    db
                ).history(
                    athlete_id=
                        athlete_id,
                    week_id=week_id,
                )
        }

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)

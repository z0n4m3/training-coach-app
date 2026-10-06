import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.weekly_review_service import (
    WeeklyReviewService,
)


router = APIRouter(
    prefix="/v1/weekly-reviews",
    tags=["weekly-reviews"],
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


@router.get("/{week_id}")
def get_weekly_review(
    week_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        result = WeeklyReviewService(
            db
        ).get(
            athlete_id=athlete_id,
            week_id=week_id,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Weekly review "
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


@router.post("/{week_id}/rebuild")
def rebuild_weekly_review(
    week_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return WeeklyReviewService(
            db
        ).rebuild(
            athlete_id=athlete_id,
            week_id=week_id,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)

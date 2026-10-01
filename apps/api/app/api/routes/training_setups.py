import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.training_setup import (
    TrainingSetupCreate,
)
from app.services.training_setup_service import (
    TrainingSetupService,
)


router = APIRouter(
    prefix="/v1/cycling/setups",
    tags=["cycling-setups"],
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
def create_setup(
    payload: TrainingSetupCreate,
    db: Session = Depends(get_db),
):
    try:
        return TrainingSetupService(
            db
        ).create(
            payload
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("")
def list_setups(
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return {
            "items":
                TrainingSetupService(
                    db
                ).list(
                    athlete_id
                )
        }

    except LookupError as exc:
        _handle_error(exc)


@router.get("/{setup_id}")
def get_setup(
    setup_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return TrainingSetupService(
            db
        ).get(
            athlete_id,
            setup_id,
        )

    except LookupError as exc:
        _handle_error(exc)

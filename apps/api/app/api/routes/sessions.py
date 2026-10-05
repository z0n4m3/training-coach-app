import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.session_context import (
    SessionTrainingSetupUpdate,
)
from app.schemas.session_feedback import (
    SessionFeedbackUpdate,
)
from app.services.session_context_service import (
    SessionContextService,
)
from app.services.session_feedback_service import (
    SessionFeedbackService,
)
from app.services.session_query_service import SessionQueryService

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.get("")
def list_sessions(
    athlete_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    from_at: datetime | None = Query(default=None),
    to_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(
            status_code=400,
            detail="from_at must be earlier than or equal to to_at",
        )

    items = SessionQueryService(db).list_sessions(
        athlete_id=athlete_id,
        limit=limit,
        from_at=from_at,
        to_at=to_at,
    )

    return {
        "items": items,
        "count": len(items),
    }


@router.patch(
    "/{session_id}/training-setup"
)
def set_training_setup(
    session_id: uuid.UUID,
    athlete_id: uuid.UUID,
    payload: SessionTrainingSetupUpdate,
    db: Session = Depends(get_db),
):
    try:
        return SessionContextService(
            db
        ).set_training_setup(
            athlete_id=athlete_id,
            session_id=session_id,
            training_setup_id=
                payload.training_setup_id,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{session_id}/feedback"
)
def update_session_feedback(
    session_id: uuid.UUID,
    athlete_id: uuid.UUID,
    payload: SessionFeedbackUpdate,
    db: Session = Depends(get_db),
):
    try:
        return SessionFeedbackService(
            db
        ).update(
            athlete_id=athlete_id,
            session_id=session_id,
            payload=payload,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/{session_id}")
def get_session(
    session_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    session = SessionQueryService(db).get_session(
        athlete_id=athlete_id,
        session_id=session_id,
    )

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session

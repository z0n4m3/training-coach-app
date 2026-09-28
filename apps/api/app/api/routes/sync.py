import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.sync_service import IntervalsSyncService

router = APIRouter(prefix="/v1/sync", tags=["sync"])


@router.post("/intervals")
def sync_intervals(
    athlete_id: uuid.UUID,
    days: int = Query(default=7, ge=1, le=31),
    source_preference: str = Query(default="auto"),
    db: Session = Depends(get_db),
):
    try:
        return IntervalsSyncService(db).sync(athlete_id=athlete_id, days=days, source_preference=source_preference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

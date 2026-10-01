import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.plan import (
    GoalEventCreate,
    MacrocycleCreate,
    PlannedSessionCreate,
    SeasonCreate,
    TrainingWeekCreate,
)
from app.services.plan_service import PlanService


router = APIRouter(prefix="/v1/plans", tags=["plans"])


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


@router.post("/seasons", status_code=201)
def create_season(
    payload: SeasonCreate,
    db: Session = Depends(get_db),
):
    try:
        return PlanService(db).create_season(payload)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.get("/seasons")
def list_seasons(
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return {
        "items": PlanService(db).list_seasons(athlete_id),
    }


@router.get("/seasons/{season_id}")
def get_season(
    season_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return PlanService(db).get_season_tree(
            season_id,
            athlete_id,
        )
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post(
    "/seasons/{season_id}/goal-events",
    status_code=201,
)
def create_goal_event(
    season_id: uuid.UUID,
    athlete_id: uuid.UUID,
    payload: GoalEventCreate,
    db: Session = Depends(get_db),
):
    try:
        return PlanService(db).create_goal_event(
            season_id,
            athlete_id,
            payload,
        )
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post(
    "/seasons/{season_id}/macrocycles",
    status_code=201,
)
def create_macrocycle(
    season_id: uuid.UUID,
    athlete_id: uuid.UUID,
    payload: MacrocycleCreate,
    db: Session = Depends(get_db),
):
    try:
        return PlanService(db).create_macrocycle(
            season_id,
            athlete_id,
            payload,
        )
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post(
    "/macrocycles/{macrocycle_id}/weeks",
    status_code=201,
)
def create_training_week(
    macrocycle_id: uuid.UUID,
    athlete_id: uuid.UUID,
    payload: TrainingWeekCreate,
    db: Session = Depends(get_db),
):
    try:
        return PlanService(db).create_training_week(
            macrocycle_id,
            athlete_id,
            payload,
        )
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post(
    "/weeks/{week_id}/sessions",
    status_code=201,
)
def create_planned_session(
    week_id: uuid.UUID,
    athlete_id: uuid.UUID,
    payload: PlannedSessionCreate,
    db: Session = Depends(get_db),
):
    try:
        return PlanService(db).create_planned_session(
            week_id,
            athlete_id,
            payload,
        )
    except (LookupError, ValueError) as exc:
        _handle_error(exc)

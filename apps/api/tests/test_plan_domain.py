from datetime import date, datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    GoalEvent,
    Macrocycle,
    PlannedSession,
    Season,
    TrainingWeek,
    User,
)


def make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_plan_domain_hierarchy_can_be_persisted():
    db = make_db()

    user = User(timezone="Europe/Warsaw")
    db.add(user)
    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Test Athlete",
    )
    db.add(athlete)
    db.flush()

    season = Season(
        athlete_id=athlete.id,
        name="Ultra 2027",
        start_date=date(2026, 11, 23),
        end_date=date(2027, 10, 31),
        status="planning",
    )
    db.add(season)
    db.flush()

    event = GoalEvent(
        season_id=season.id,
        athlete_id=athlete.id,
        name="RAP900",
        event_start_at=datetime(
            2027,
            6,
            1,
            6,
            0,
            tzinfo=timezone.utc,
        ),
        priority="A",
        distance_km=900,
        goal_text="Primary ultra goal",
    )
    db.add(event)

    macrocycle = Macrocycle(
        season_id=season.id,
        athlete_id=athlete.id,
        name="Base 1",
        sequence=1,
        start_date=date(2026, 11, 23),
        end_date=date(2027, 1, 17),
        objective="Aerobic base and strength",
    )
    db.add(macrocycle)
    db.flush()

    week = TrainingWeek(
        macrocycle_id=macrocycle.id,
        athlete_id=athlete.id,
        week_number=1,
        start_date=date(2026, 11, 23),
        end_date=date(2026, 11, 29),
    )
    db.add(week)
    db.flush()

    planned = PlannedSession(
        training_week_id=week.id,
        athlete_id=athlete.id,
        planned_start_at=datetime(
            2026,
            11,
            24,
            17,
            0,
            tzinfo=timezone.utc,
        ),
        name="END 75'",
        sport="cycling",
        session_type="END",
        priority="SUPPORT",
        planned_duration_s=4500,
        targets={
            "intensity": "endurance",
            "rpe": [2, 3],
        },
        workout_structure={
            "type": "steady",
            "duration_s": 4500,
        },
    )
    db.add(planned)

    db.commit()

    stored_season = db.scalar(select(Season))
    stored_event = db.scalar(select(GoalEvent))
    stored_macrocycle = db.scalar(select(Macrocycle))
    stored_week = db.scalar(select(TrainingWeek))
    stored_session = db.scalar(select(PlannedSession))

    assert stored_season.name == "Ultra 2027"
    assert stored_event.name == "RAP900"
    assert stored_event.priority == "A"
    assert stored_macrocycle.sequence == 1
    assert stored_week.week_number == 1

    assert stored_session.session_type == "END"
    assert stored_session.priority == "SUPPORT"
    assert stored_session.planned_duration_s == 4500
    assert stored_session.targets["rpe"] == [2, 3]
    assert stored_session.workout_structure["type"] == "steady"

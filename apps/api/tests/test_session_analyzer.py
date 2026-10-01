from datetime import date, datetime, timezone

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CanonicalSession,
    Macrocycle,
    PlannedSession,
    Season,
    SessionAnalysis,
    SessionMatch,
    TrainingWeek,
    User,
)
from app.services.session_analyzer import SessionAnalyzer


def make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    @event.listens_for(engine, "connect")
    def _fk_on(
        dbapi_connection,
        connection_record,
    ):
        cursor = dbapi_connection.cursor()
        cursor.execute(
            "PRAGMA foreign_keys=ON"
        )
        cursor.close()

    Base.metadata.create_all(engine)

    return Session(engine)


def make_athlete(db: Session) -> Athlete:
    user = User(
        timezone="Europe/Warsaw"
    )
    db.add(user)
    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Test Athlete",
    )
    db.add(athlete)
    db.commit()

    return athlete


def make_plan(
    db: Session,
    athlete: Athlete,
    *,
    duration_s: float | None = 4500,
    distance_m: float | None = None,
) -> PlannedSession:
    season = Season(
        athlete_id=athlete.id,
        name="Ultra 2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 10, 31),
    )
    db.add(season)
    db.flush()

    macrocycle = Macrocycle(
        season_id=season.id,
        athlete_id=athlete.id,
        name="Base",
        sequence=1,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 10, 31),
    )
    db.add(macrocycle)
    db.flush()

    week = TrainingWeek(
        macrocycle_id=macrocycle.id,
        athlete_id=athlete.id,
        week_number=1,
        start_date=date(2026, 9, 28),
        end_date=date(2026, 10, 4),
    )
    db.add(week)
    db.flush()

    plan = PlannedSession(
        training_week_id=week.id,
        athlete_id=athlete.id,
        planned_start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        name="END",
        sport="cycling",
        session_type="END",
        priority="SUPPORT",
        status="completed",
        planned_duration_s=duration_s,
        planned_distance_m=distance_m,
        targets={
            "intensity": "endurance",
        },
    )

    db.add(plan)
    db.commit()

    return plan


def make_session(
    db: Session,
    athlete: Athlete,
    *,
    duration_s: float = 4500,
    distance_m: float | None = None,
    fingerprint: str = "analysis-session",
) -> CanonicalSession:
    session = CanonicalSession(
        athlete_id=athlete.id,
        sport="Ride",
        start_at=datetime(
            2026,
            9,
            28,
            16,
            5,
            tzinfo=timezone.utc,
        ),
        duration_s=duration_s,
        distance_m=distance_m,
        training_load=70,
        avg_power_w=200,
        normalized_power_w=210,
        duplicate_status="single",
        fingerprint=fingerprint,
    )

    db.add(session)
    db.commit()

    return session


def link(
    db: Session,
    athlete: Athlete,
    plan: PlannedSession,
    session: CanonicalSession,
):
    db.add(
        SessionMatch(
            athlete_id=athlete.id,
            planned_session_id=plan.id,
            canonical_session_id=session.id,
            match_method="auto_score",
            match_score=0.95,
            manual_override=False,
        )
    )
    db.commit()


def test_session_with_no_plan_is_unplanned():
    db = make_db()
    athlete = make_athlete(db)

    session = make_session(
        db,
        athlete,
    )

    result = SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis)
    )

    assert result["unplanned"] == 1
    assert analysis.classification == "unplanned"
    assert analysis.planned_session_id is None
    assert (
        "no_planned_session_match"
        in analysis.flags
    )


def test_duration_close_to_plan_is_on_plan():
    db = make_db()
    athlete = make_athlete(db)

    plan = make_plan(
        db,
        athlete,
        duration_s=4500,
    )

    session = make_session(
        db,
        athlete,
        duration_s=4300,
    )

    link(
        db,
        athlete,
        plan,
        session,
    )

    result = SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis)
    )

    assert result["on_plan"] == 1
    assert analysis.classification == "on_plan"

    duration = analysis.evidence[
        "comparisons"
    ]["duration"]

    assert duration["level"] == "within"


def test_large_duration_difference_is_major_modification():
    db = make_db()
    athlete = make_athlete(db)

    plan = make_plan(
        db,
        athlete,
        duration_s=7200,
    )

    session = make_session(
        db,
        athlete,
        duration_s=3600,
    )

    link(
        db,
        athlete,
        plan,
        session,
    )

    result = SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis)
    )

    assert result["modified_major"] == 1
    assert (
        analysis.classification
        == "modified_major"
    )
    assert (
        "duration_under_major"
        in analysis.flags
    )


def test_analysis_is_updated_instead_of_duplicated():
    db = make_db()
    athlete = make_athlete(db)

    plan = make_plan(
        db,
        athlete,
        duration_s=4500,
    )

    session = make_session(
        db,
        athlete,
        duration_s=4500,
    )

    link(
        db,
        athlete,
        plan,
        session,
    )

    analyzer = SessionAnalyzer(db)

    analyzer.analyze(
        athlete.id,
        {session.id},
    )
    db.commit()

    first = db.scalar(
        select(SessionAnalysis)
    )

    first_id = first.id

    session.duration_s = 2500
    db.commit()

    analyzer.analyze(
        athlete.id,
        {session.id},
    )
    db.commit()
    db.expire_all()

    analyses = list(
        db.scalars(
            select(SessionAnalysis)
        )
    )

    assert len(analyses) == 1
    assert analyses[0].id == first_id
    assert (
        analyses[0].classification
        == "modified_major"
    )


def test_multiple_plan_matches_are_not_guessed():
    db = make_db()
    athlete = make_athlete(db)

    first_plan = make_plan(
        db,
        athlete,
        duration_s=4500,
    )

    session = make_session(
        db,
        athlete,
        duration_s=4500,
    )

    link(
        db,
        athlete,
        first_plan,
        session,
    )

    second_plan = PlannedSession(
        training_week_id=
            first_plan.training_week_id,
        athlete_id=athlete.id,
        planned_start_at=datetime(
            2026,
            9,
            28,
            17,
            0,
            tzinfo=timezone.utc,
        ),
        name="Second plan",
        sport="cycling",
        priority="SUPPORT",
        status="completed",
        planned_duration_s=4500,
    )
    db.add(second_plan)
    db.flush()

    db.add(
        SessionMatch(
            athlete_id=athlete.id,
            planned_session_id=second_plan.id,
            canonical_session_id=session.id,
            match_method="manual",
            manual_override=True,
        )
    )
    db.commit()

    result = SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis)
    )

    assert result["match_conflict"] == 1
    assert (
        analysis.classification
        == "match_conflict"
    )
    assert (
        analysis.planned_session_id
        is None
    )

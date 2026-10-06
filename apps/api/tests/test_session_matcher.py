from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CanonicalSession,
    CanonicalSessionSource,
    Macrocycle,
    PlannedSession,
    Season,
    SessionMatch,
    SourceActivity,
    TrainingWeek,
    User,
)
from app.services.session_matcher import SessionMatcher


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


def make_plan(
    db: Session,
    *,
    planned_start_at: datetime,
    duration_s: float | None = 4500,
    intervals_event_id: str | None = None,
    sport: str = "cycling",
) -> tuple[Athlete, PlannedSession]:
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
    db.flush()

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

    planned = PlannedSession(
        training_week_id=week.id,
        athlete_id=athlete.id,
        planned_start_at=planned_start_at,
        name="END 75",
        sport=sport,
        priority="SUPPORT",
        status="planned",
        planned_duration_s=duration_s,
        intervals_event_id=intervals_event_id,
    )
    db.add(planned)
    db.commit()

    return athlete, planned


def add_canonical(
    db: Session,
    athlete: Athlete,
    *,
    start_at: datetime,
    duration_s: float = 4200,
    sport: str = "Ride",
    fingerprint: str,
) -> CanonicalSession:
    canonical = CanonicalSession(
        athlete_id=athlete.id,
        sport=sport,
        start_at=start_at,
        duration_s=duration_s,
        duplicate_status="single",
        fingerprint=fingerprint,
    )
    db.add(canonical)
    db.commit()

    return canonical


def test_scored_match_normalizes_cycling_sport():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            28,
            16,
            15,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
    )

    canonical = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4200,
        sport="Ride",
        fingerprint="score-match",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {canonical.id},
    )

    db.commit()
    db.expire_all()

    match = db.scalar(
        select(SessionMatch).where(
            SessionMatch.planned_session_id
            == planned.id
        )
    )

    assert result["matched"] == 1
    assert result["matched_by_score"] == 1
    assert match is not None
    assert (
        match.canonical_session_id
        == canonical.id
    )
    assert match.match_method == "auto_score"
    assert match.match_score >= 0.82

    persisted_plan = db.get(
        PlannedSession,
        planned.id,
    )

    assert persisted_plan.status == "completed"


def test_exact_intervals_event_id_has_priority():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            28,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        intervals_event_id="event-123",
    )

    canonical = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        fingerprint="event-match",
    )

    source = SourceActivity(
        athlete_id=athlete.id,
        provider="intervals",
        provider_activity_id="activity-123",
        recording_source="Garmin",
        sport="Ride",
        start_at=canonical.start_at,
        duration_s=4200,
        paired_event_id="event-123",
        raw_payload={},
        payload_hash="hash-event-123",
    )

    db.add(source)
    db.flush()

    db.add(
        CanonicalSessionSource(
            canonical_session_id=canonical.id,
            source_activity_id=source.id,
            role="PRIMARY",
            duplicate_score=None,
            manual_override=False,
        )
    )
    db.commit()

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {canonical.id},
    )

    db.commit()

    match = db.scalar(
        select(SessionMatch).where(
            SessionMatch.planned_session_id
            == planned.id
        )
    )

    assert result["matched"] == 1
    assert result["matched_by_event_id"] == 1
    assert match.match_method == "intervals_event"
    assert match.match_score == 1.0


def test_ambiguous_candidates_are_not_auto_matched():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
    )

    first = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            28,
            15,
            50,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
        fingerprint="ambiguous-1",
    )

    second = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            28,
            16,
            10,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
        fingerprint="ambiguous-2",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {
            first.id,
            second.id,
        },
    )

    db.commit()

    match = db.scalar(
        select(SessionMatch).where(
            SessionMatch.planned_session_id
            == planned.id
        )
    )

    assert result["matched"] == 0
    assert result["ambiguous"] == 1
    assert match is None

    persisted_plan = db.get(
        PlannedSession,
        planned.id,
    )

    assert persisted_plan.status == "planned"


def test_wrong_sport_is_not_matched():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        sport="cycling",
    )

    canonical = add_canonical(
        db,
        athlete,
        start_at=planned.planned_start_at
        + timedelta(minutes=5),
        sport="Run",
        fingerprint="wrong-sport",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {canonical.id},
    )

    db.commit()

    assert result["matched"] == 0
    assert result["no_candidate"] == 1

    assert db.scalar(
        select(SessionMatch)
    ) is None


def test_existing_manual_match_is_never_replaced():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
    )

    original = add_canonical(
        db,
        athlete,
        start_at=planned.planned_start_at,
        fingerprint="manual-original",
    )

    alternative = add_canonical(
        db,
        athlete,
        start_at=planned.planned_start_at,
        fingerprint="manual-alternative",
    )

    manual = SessionMatch(
        athlete_id=athlete.id,
        planned_session_id=planned.id,
        canonical_session_id=original.id,
        match_method="manual",
        manual_override=True,
        match_evidence={
            "reason": "user choice"
        },
    )
    db.add(manual)
    db.commit()

    SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {alternative.id},
    )

    db.commit()
    db.expire_all()

    matches = list(
        db.scalars(
            select(SessionMatch).where(
                SessionMatch.planned_session_id
                == planned.id
            )
        )
    )

    assert len(matches) == 1
    assert (
        matches[0].canonical_session_id
        == original.id
    )
    assert matches[0].manual_override is True


def test_session_can_move_to_another_day_inside_same_week():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
    )

    canonical = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            10,
            4,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4050,
        sport="Ride",
        fingerprint=
            "shifted-within-week",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {canonical.id},
    )

    db.commit()

    match = db.scalar(
        select(
            SessionMatch
        ).where(
            SessionMatch
            .planned_session_id
            == planned.id
        )
    )

    assert result["matched"] == 1
    assert match is not None

    assert (
        match.canonical_session_id
        == canonical.id
    )

    assert (
        match.match_evidence[
            "schedule_policy"
        ]
        == "flexible_within_week"
    )

    assert (
        match.match_evidence[
            "schedule_shifted"
        ]
        is True
    )

    assert (
        match.match_evidence[
            "day_shift"
        ]
        == 6
    )

    assert (
        match.match_evidence[
            "duration_score"
        ]
        == 1.0
    )


def test_two_cycling_sessions_can_swap_days_when_volume_identifies_them():
    db = make_db()

    athlete, first_plan = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=3600,
    )

    second_plan = PlannedSession(
        training_week_id=
            first_plan.training_week_id,
        athlete_id=athlete.id,
        planned_start_at=datetime(
            2026,
            9,
            29,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        name="LONG END",
        sport="cycling",
        priority="KEY",
        status="planned",
        planned_duration_s=5400,
    )

    db.add(second_plan)
    db.commit()

    longer_on_monday = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=5400,
        sport="Ride",
        fingerprint=
            "longer-on-monday",
    )

    shorter_on_tuesday = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            29,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=3600,
        sport="Ride",
        fingerprint=
            "shorter-on-tuesday",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {
            longer_on_monday.id,
            shorter_on_tuesday.id,
        },
    )

    db.commit()

    matches = list(
        db.scalars(
            select(
                SessionMatch
            ).where(
                SessionMatch.athlete_id
                == athlete.id
            )
        )
    )

    by_plan = {
        item.planned_session_id:
            item
        for item in matches
    }

    assert result["matched"] == 2

    assert (
        by_plan[
            first_plan.id
        ].canonical_session_id
        == shorter_on_tuesday.id
    )

    assert (
        by_plan[
            second_plan.id
        ].canonical_session_id
        == longer_on_monday.id
    )

    assert (
        by_plan[
            first_plan.id
        ].match_evidence[
            "day_shift"
        ]
        == 1
    )

    assert (
        by_plan[
            second_plan.id
        ].match_evidence[
            "day_shift"
        ]
        == -1
    )


def test_strength_and_cycling_can_swap_days_inside_week():
    db = make_db()

    athlete, strength_plan = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            29,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=3600,
        sport="strength",
    )

    cycling_plan = PlannedSession(
        training_week_id=
            strength_plan.training_week_id,
        athlete_id=athlete.id,
        planned_start_at=datetime(
            2026,
            9,
            30,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        name="END",
        sport="cycling",
        priority="SUPPORT",
        status="planned",
        planned_duration_s=5400,
    )

    db.add(cycling_plan)
    db.commit()

    cycling_on_tuesday = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            29,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=5400,
        sport="Ride",
        fingerprint=
            "cycling-on-strength-day",
    )

    strength_on_wednesday = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            30,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=3600,
        sport="WeightTraining",
        fingerprint=
            "strength-on-cycling-day",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {
            cycling_on_tuesday.id,
            strength_on_wednesday.id,
        },
    )

    db.commit()

    matches = list(
        db.scalars(
            select(
                SessionMatch
            ).where(
                SessionMatch.athlete_id
                == athlete.id
            )
        )
    )

    by_plan = {
        item.planned_session_id:
            item
        for item in matches
    }

    assert result["matched"] == 2

    assert (
        by_plan[
            strength_plan.id
        ].canonical_session_id
        == strength_on_wednesday.id
    )

    assert (
        by_plan[
            cycling_plan.id
        ].canonical_session_id
        == cycling_on_tuesday.id
    )

    assert (
        by_plan[
            strength_plan.id
        ].match_evidence[
            "planned_sport"
        ]
        == "strength"
    )

    assert (
        by_plan[
            strength_plan.id
        ].match_evidence[
            "actual_sport"
        ]
        == "strength"
    )


def test_heuristic_matching_does_not_cross_week_boundary():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            10,
            4,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
    )

    canonical = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            10,
            5,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
        sport="Ride",
        fingerprint=
            "next-week",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {canonical.id},
    )

    db.commit()

    match = db.scalar(
        select(
            SessionMatch
        ).where(
            SessionMatch
            .planned_session_id
            == planned.id
        )
    )

    assert result["matched"] == 0
    assert result["no_candidate"] == 1
    assert match is None


def test_similar_week_sessions_remain_ambiguous():
    db = make_db()

    athlete, planned = make_plan(
        db,
        planned_start_at=datetime(
            2026,
            9,
            29,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
    )

    first = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            28,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
        fingerprint=
            "similar-before",
    )

    second = add_canonical(
        db,
        athlete,
        start_at=datetime(
            2026,
            9,
            30,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=4500,
        fingerprint=
            "similar-after",
    )

    result = SessionMatcher(
        db
    ).auto_match(
        athlete.id,
        {
            first.id,
            second.id,
        },
    )

    db.commit()

    assert result["matched"] == 0
    assert result["ambiguous"] == 1

    assert db.scalar(
        select(
            SessionMatch
        ).where(
            SessionMatch
            .planned_session_id
            == planned.id
        )
    ) is None

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
from app.schemas.performance import ZoneSetCreate
from app.services.performance_profile_service import (
    PerformanceProfileService,
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

    assert result["matched"] == 1
    assert result["duration_within"] == 1
    assert analysis.classification == "matched"

    duration = analysis.evidence[
        "duration_assessment"
    ]["comparison"]

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

    assert result["matched"] == 1
    assert result["duration_major"] == 1
    assert (
        analysis.classification
        == "matched"
    )
    assert (
        analysis.evidence[
            "duration_assessment"
        ]["status"]
        == "major"
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
        == "matched"
    )
    assert (
        analyses[0].evidence[
            "duration_assessment"
        ]["status"]
        == "major"
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


def test_indoor_session_uses_historical_indoor_ftp():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    service.create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="indoor",
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=230,
            threshold_hr_bpm=178,
            source="test",
        )
    )

    # Future FTP version must NOT affect
    # the September session.
    service.create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="indoor",
            effective_from=datetime(
                2026,
                10,
                15,
                tzinfo=timezone.utc,
            ),
            ftp_w=240,
            threshold_hr_bpm=180,
            source="test",
        )
    )

    session = make_session(
        db,
        athlete,
        duration_s=4500,
        fingerprint="indoor-intensity",
    )

    session.indoor = True
    session.avg_power_w = 184
    session.normalized_power_w = 207
    session.avg_hr_bpm = 150
    session.max_hr_bpm = 176

    db.commit()

    SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    performance = analysis.evidence[
        "performance"
    ]

    assert (
        analysis.analysis_version
        == "deterministic-v3"
    )

    assert (
        performance["context"]
        == "indoor"
    )

    assert (
        performance["ftp_w"]
        == 230
    )

    assert (
        performance[
            "threshold_hr_bpm"
        ]
        == 178
    )

    assert (
        performance[
            "avg_power_pct_ftp"
        ]
        == 80.0
    )

    assert (
        performance[
            "normalized_power_pct_ftp"
        ]
        == 90.0
    )

    assert (
        performance[
            "intensity_factor"
        ]
        == 0.9
    )

    assert (
        performance[
            "avg_hr_pct_threshold"
        ]
        == 84.27
    )

    assert (
        performance[
            "max_hr_pct_threshold"
        ]
        == 98.88
    )

    assert (
        performance[
            "effective_from"
        ].startswith("2026-09-01")
    )


def test_outdoor_session_uses_outdoor_profile():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    service.create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="indoor",
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=230,
            source="test",
        )
    )

    service.create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="outdoor",
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=250,
            source="test",
        )
    )

    session = make_session(
        db,
        athlete,
        fingerprint="outdoor-intensity",
    )

    session.indoor = False
    session.avg_power_w = 175
    session.normalized_power_w = 200

    db.commit()

    SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    performance = analysis.evidence[
        "performance"
    ]

    assert (
        performance["context"]
        == "outdoor"
    )

    assert (
        performance["ftp_w"]
        == 250
    )

    assert (
        performance[
            "avg_power_pct_ftp"
        ]
        == 70.0
    )

    assert (
        performance[
            "normalized_power_pct_ftp"
        ]
        == 80.0
    )

    assert (
        performance[
            "intensity_factor"
        ]
        == 0.8
    )


def test_session_without_effective_profile_is_not_guessed():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    service.create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="outdoor",
            effective_from=datetime(
                2026,
                10,
                15,
                tzinfo=timezone.utc,
            ),
            ftp_w=255,
            source="test",
        )
    )

    session = make_session(
        db,
        athlete,
        fingerprint="no-old-profile",
    )

    session.indoor = False

    db.commit()

    SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    performance = analysis.evidence[
        "performance"
    ]

    assert (
        performance["status"]
        == "zone_set_missing"
    )

    assert (
        performance["ftp_w"]
        is None
    )

    assert (
        "no_effective_zone_set"
        in analysis.flags
    )


def test_unknown_indoor_outdoor_context_is_not_guessed():
    db = make_db()
    athlete = make_athlete(db)

    session = make_session(
        db,
        athlete,
        fingerprint="unknown-context",
    )

    session.indoor = None

    db.commit()

    SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    performance = analysis.evidence[
        "performance"
    ]

    assert (
        performance["status"]
        == "context_unknown"
    )

    assert (
        "performance_context_unknown"
        in analysis.flags
    )


def test_distance_does_not_affect_training_compliance():
    db = make_db()
    athlete = make_athlete(db)

    plan = make_plan(
        db,
        athlete,
        duration_s=4500,
        distance_m=100000,
    )

    session = make_session(
        db,
        athlete,
        duration_s=4500,
        distance_m=25000,
        fingerprint="distance-not-target",
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
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    assert result["matched"] == 1
    assert result["duration_within"] == 1

    assert (
        analysis.evidence[
            "duration_assessment"
        ]["status"]
        == "within"
    )


def test_steady_power_and_hr_targets_are_assessed_separately():
    db = make_db()
    athlete = make_athlete(db)

    PerformanceProfileService(
        db
    ).create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="outdoor",
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=250,
            threshold_hr_bpm=178,
            source="test",
        )
    )

    plan = make_plan(
        db,
        athlete,
        duration_s=4500,
    )

    plan.targets = {
        "power": {
            "metric":
                "avg_power_pct_ftp",
            "min": 60,
            "max": 72,
        },
        "hr": {
            "metric":
                "avg_hr_pct_threshold",
            "min": 70,
            "max": 85,
        },
    }

    plan.workout_structure = {
        "type": "steady",
    }

    session = make_session(
        db,
        athlete,
        duration_s=4500,
        fingerprint="too-hard-steady",
    )

    session.indoor = False
    session.avg_power_w = 205
    session.avg_hr_bpm = 150

    db.commit()

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
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    stimulus = analysis.evidence[
        "stimulus_assessment"
    ]

    assert result["duration_within"] == 1

    assert (
        stimulus["power"]["status"]
        == "above_target"
    )

    assert (
        stimulus["hr"]["status"]
        == "aligned"
    )

    assert (
        stimulus["status"]
        == "above_target"
    )


def test_power_hr_disagreement_is_preserved():
    db = make_db()
    athlete = make_athlete(db)

    PerformanceProfileService(
        db
    ).create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="outdoor",
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=250,
            threshold_hr_bpm=178,
            source="test",
        )
    )

    plan = make_plan(
        db,
        athlete,
    )

    plan.targets = {
        "power": {
            "metric":
                "avg_power_pct_ftp",
            "min": 65,
            "max": 75,
        },
        "hr": {
            "metric":
                "avg_hr_pct_threshold",
            "min": 75,
            "max": 85,
        },
    }

    plan.workout_structure = {
        "type": "steady",
    }

    session = make_session(
        db,
        athlete,
        fingerprint="mixed-response",
    )

    session.indoor = False
    session.avg_power_w = 190
    session.avg_hr_bpm = 125

    db.commit()

    link(
        db,
        athlete,
        plan,
        session,
    )

    SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    stimulus = analysis.evidence[
        "stimulus_assessment"
    ]

    assert (
        stimulus["power"]["status"]
        == "above_target"
    )

    assert (
        stimulus["hr"]["status"]
        == "below_target"
    )

    assert (
        stimulus["status"]
        == "mixed"
    )

    assert (
        "power_above_target"
        in analysis.flags
    )

    assert (
        "hr_below_target"
        in analysis.flags
    )


def test_interval_workout_is_not_judged_from_session_average():
    db = make_db()
    athlete = make_athlete(db)

    plan = make_plan(
        db,
        athlete,
    )

    plan.session_type = "THRESHOLD"

    plan.targets = {
        "power": {
            "metric":
                "avg_power_pct_ftp",
            "min": 95,
            "max": 105,
        }
    }

    plan.workout_structure = {
        "type": "intervals",
        "steps": [
            {
                "repeats": 4,
                "work_s": 600,
                "recovery_s": 300,
            }
        ],
    }

    session = make_session(
        db,
        athlete,
        fingerprint="interval-safe",
    )

    link(
        db,
        athlete,
        plan,
        session,
    )

    SessionAnalyzer(
        db
    ).analyze(
        athlete.id,
        {session.id},
    )

    db.commit()

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    assert (
        analysis.evidence[
            "stimulus_assessment"
        ]["status"]
        == "interval_analysis_required"
    )

    assert (
        "stimulus_requires_interval_analysis"
        in analysis.flags
    )

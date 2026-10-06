from datetime import (
    date,
    datetime,
    timezone,
)

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CanonicalSession,
    Macrocycle,
    PlannedSession,
    Season,
    SessionAnalysis,
    SessionFeedback,
    SessionMatch,
    TrainingWeek,
    User,
    WeeklyReview,
)
from app.services.weekly_review_service import (
    WeeklyReviewService,
    _build_coach_kpis,
)


def make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    return Session(engine)


def make_week(
    db: Session,
):
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
        start_date=date(
            2026,
            9,
            1,
        ),
        end_date=date(
            2027,
            10,
            31,
        ),
    )

    db.add(season)
    db.flush()

    macro = Macrocycle(
        season_id=season.id,
        athlete_id=athlete.id,
        name="Base",
        sequence=1,
        start_date=date(
            2026,
            9,
            1,
        ),
        end_date=date(
            2026,
            10,
            31,
        ),
    )

    db.add(macro)
    db.flush()

    week = TrainingWeek(
        macrocycle_id=macro.id,
        athlete_id=athlete.id,
        week_number=5,
        start_date=date(
            2026,
            9,
            28,
        ),
        end_date=date(
            2026,
            10,
            4,
        ),
    )

    db.add(week)
    db.commit()

    return (
        user,
        athlete,
        week,
    )


def add_plan(
    db: Session,
    athlete: Athlete,
    week: TrainingWeek,
    *,
    name: str,
    sport: str,
    priority: str,
    day: int,
    duration_s: float,
):
    item = PlannedSession(
        training_week_id=week.id,
        athlete_id=athlete.id,
        planned_start_at=datetime(
            2026,
            9,
            day,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        name=name,
        sport=sport,
        session_type=name,
        priority=priority,
        planned_duration_s=
            duration_s,
        targets={},
        workout_structure={},
    )

    db.add(item)
    db.flush()

    return item


def add_actual(
    db: Session,
    athlete: Athlete,
    *,
    fingerprint: str,
    sport: str,
    start_at: datetime,
    duration_s: float,
    training_load: float | None,
    work_kj: float | None,
    distance_m: float | None,
):
    item = CanonicalSession(
        athlete_id=athlete.id,
        sport=sport,
        indoor=False,
        start_at=start_at,
        duration_s=duration_s,
        distance_m=distance_m,
        work_kj=work_kj,
        training_load=training_load,
        fingerprint=fingerprint,
    )

    db.add(item)
    db.flush()

    return item


def test_weekly_review_focuses_on_volume_not_weekday():
    db = make_db()

    (
        _,
        athlete,
        week,
    ) = make_week(db)

    strength = add_plan(
        db,
        athlete,
        week,
        name="STRENGTH",
        sport="strength",
        priority="SUPPORT",
        day=29,
        duration_s=3600,
    )

    end = add_plan(
        db,
        athlete,
        week,
        name="END",
        sport="cycling",
        priority="SUPPORT",
        day=30,
        duration_s=5400,
    )

    add_plan(
        db,
        athlete,
        week,
        name="RECOVERY",
        sport="cycling",
        priority="EASY",
        day=28,
        duration_s=1800,
    )

    # END moves from Wednesday to Tuesday.
    actual_end = add_actual(
        db,
        athlete,
        fingerprint="end-swapped",
        sport="Ride",
        start_at=datetime(
            2026,
            9,
            29,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=5400,
        training_load=70,
        work_kj=700,
        distance_m=40000,
    )

    # Strength moves from Tuesday to Wednesday.
    actual_strength = add_actual(
        db,
        athlete,
        fingerprint="strength-swapped",
        sport="WeightTraining",
        start_at=datetime(
            2026,
            9,
            30,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=3600,
        training_load=30,
        work_kj=None,
        distance_m=None,
    )

    extra = add_actual(
        db,
        athlete,
        fingerprint="extra-spin",
        sport="Ride",
        start_at=datetime(
            2026,
            10,
            2,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=1800,
        training_load=20,
        work_kj=200,
        distance_m=15000,
    )

    db.add_all(
        [
            SessionMatch(
                athlete_id=athlete.id,
                planned_session_id=
                    strength.id,
                canonical_session_id=
                    actual_strength.id,
                match_method="auto_score",
                match_score=0.95,
                match_evidence={
                    "schedule_shifted":
                        True,
                    "day_shift": 1,
                },
            ),
            SessionMatch(
                athlete_id=athlete.id,
                planned_session_id=
                    end.id,
                canonical_session_id=
                    actual_end.id,
                match_method="auto_score",
                match_score=0.95,
                match_evidence={
                    "schedule_shifted":
                        True,
                    "day_shift": -1,
                },
            ),
        ]
    )

    db.add_all(
        [
            SessionAnalysis(
                athlete_id=athlete.id,
                canonical_session_id=
                    actual_end.id,
                planned_session_id=
                    end.id,
                analysis_version=
                    "deterministic-v6",
                classification="matched",
                evidence={
                    "duration_assessment": {
                        "status": "within"
                    },
                    "stimulus_assessment": {
                        "status": "aligned"
                    },
                    "subjective_response": {
                        "status": "available"
                    },
                },
                flags=[],
            ),
            SessionAnalysis(
                athlete_id=athlete.id,
                canonical_session_id=
                    extra.id,
                planned_session_id=None,
                analysis_version=
                    "deterministic-v6",
                classification=
                    "unplanned",
                evidence={
                    "subjective_response": {
                        "status": "missing"
                    },
                },
                flags=[
                    "no_planned_session_match"
                ],
            ),
        ]
    )

    db.add(
        SessionFeedback(
            athlete_id=athlete.id,
            canonical_session_id=
                actual_end.id,
            rpe=3,
            leg_fatigue=2,
            comment="Controlled",
            custom_metrics={
                "asymmetry": {
                    "severity": 2
                }
            },
        )
    )

    db.commit()

    review = WeeklyReviewService(
        db
    ).rebuild(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    summary = review["summary"]

    execution = summary[
        "plan_execution"
    ]

    assert (
        execution[
            "planned_session_count"
        ]
        == 3
    )

    assert (
        execution[
            "matched_planned_count"
        ]
        == 2
    )

    assert (
        execution[
            "session_completion_ratio"
        ]
        == round(
            2 / 3,
            4,
        )
    )

    assert (
        execution[
            "planned_duration_s"
        ]
        == 10800
    )

    assert (
        execution[
            "completed_planned_duration_s"
        ]
        == 9000
    )

    assert (
        execution[
            "planned_volume_completion_ratio"
        ]
        == round(
            9000 / 10800,
            4,
        )
    )

    assert (
        execution[
            "matched_actual_duration_s"
        ]
        == 9000
    )

    schedule = summary[
        "schedule"
    ]

    assert (
        schedule[
            "shifted_session_count"
        ]
        == 2
    )

    assert sorted(
        schedule["shift_days"]
    ) == [-1, 1]

    # Day swapping is informational,
    # never a compliance flag.
    assert not any(
        "schedule_shift" in flag
        for flag in review["flags"]
    )

    actual = summary[
        "actual_load_window"
    ]

    assert (
        actual["session_count"]
        == 3
    )

    assert (
        actual[
            "unplanned_session_count"
        ]
        == 1
    )

    assert (
        actual["duration_s"]
        == 10800
    )

    assert (
        actual["training_load"]
        == 120
    )

    assert (
        actual[
            "cycling_distance_m_descriptive"
        ]
        == 55000
    )

    assert (
        actual["by_sport"][
            "strength"
        ]["session_count"]
        == 1
    )

    assert (
        actual["by_sport"][
            "cycling"
        ]["session_count"]
        == 2
    )

    feedback = summary[
        "feedback"
    ]

    assert (
        feedback["feedback_count"]
        == 1
    )

    assert (
        feedback["coverage"]
        == round(
            1 / 3,
            4,
        )
    )

    # Custom athlete-specific feedback
    # remains opaque to generic rules.
    assert not any(
        "asymmetry" in flag
        for flag in review["flags"]
    )


def test_plan_execution_and_load_week_are_separate():
    db = make_db()

    (
        _,
        athlete,
        week,
    ) = make_week(db)

    plan = add_plan(
        db,
        athlete,
        week,
        name="END",
        sport="cycling",
        priority="KEY",
        day=30,
        duration_s=5400,
    )

    # Explicit/manual match may point to an
    # activity outside the original week.
    # It counts for plan execution but its
    # physical load belongs to the week in
    # which it actually happened.
    actual = add_actual(
        db,
        athlete,
        fingerprint="outside-week",
        sport="Ride",
        start_at=datetime(
            2026,
            10,
            5,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=5400,
        training_load=70,
        work_kj=700,
        distance_m=40000,
    )

    db.add(
        SessionMatch(
            athlete_id=athlete.id,
            planned_session_id=
                plan.id,
            canonical_session_id=
                actual.id,
            match_method="manual",
            match_score=None,
            match_evidence={
                "reason":
                    "explicit athlete choice"
            },
            manual_override=True,
        )
    )

    db.commit()

    review = WeeklyReviewService(
        db
    ).rebuild(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert (
        review["summary"][
            "plan_execution"
        ][
            "matched_planned_count"
        ]
        == 1
    )

    assert (
        review["summary"][
            "plan_execution"
        ][
            "planned_volume_completion_ratio"
        ]
        == 1.0
    )

    assert (
        review["summary"][
            "actual_load_window"
        ]["session_count"]
        == 0
    )

    assert (
        review["summary"][
            "schedule"
        ][
            "matched_outside_load_window_count"
        ]
        == 1
    )

    assert (
        "matched_outside_load_window_present"
        in review["flags"]
    )


def test_week_window_uses_athlete_timezone():
    db = make_db()

    (
        _,
        athlete,
        week,
    ) = make_week(db)

    # Warsaw on 2026-10-04 is UTC+2.
    # 21:30 UTC = Sunday 23:30 local.
    add_actual(
        db,
        athlete,
        fingerprint="inside",
        sport="Ride",
        start_at=datetime(
            2026,
            10,
            4,
            21,
            30,
            tzinfo=timezone.utc,
        ),
        duration_s=1800,
        training_load=20,
        work_kj=150,
        distance_m=10000,
    )

    # 22:30 UTC = Monday 00:30 local.
    add_actual(
        db,
        athlete,
        fingerprint="outside",
        sport="Ride",
        start_at=datetime(
            2026,
            10,
            4,
            22,
            30,
            tzinfo=timezone.utc,
        ),
        duration_s=1800,
        training_load=20,
        work_kj=150,
        distance_m=10000,
    )

    db.commit()

    review = WeeklyReviewService(
        db
    ).rebuild(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert (
        review["summary"][
            "actual_load_window"
        ]["session_count"]
        == 1
    )

    assert (
        review["summary"][
            "actual_load_window"
        ][
            "cycling_distance_m_descriptive"
        ]
        == 10000
    )


def test_weekly_review_rebuild_is_idempotent():
    db = make_db()

    (
        _,
        athlete,
        week,
    ) = make_week(db)

    service = WeeklyReviewService(
        db
    )

    first = service.rebuild(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    second = service.rebuild(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    rows = list(
        db.scalars(
            select(
                WeeklyReview
            )
        )
    )

    assert first["id"] == second["id"]
    assert len(rows) == 1

    assert (
        second["review_version"]
        == "deterministic-weekly-v2"
    )


def test_weekly_coach_kpis_are_decision_inputs():
    summary = {
        "week": {
            "period_status":
                "complete",
        },

        "plan_execution": {
            "planned_session_count":
                4,
            "matched_planned_count":
                3,
            "unmatched_planned_count":
                1,
            "session_completion_ratio":
                0.75,

            "planned_duration_s":
                14400,
            "planned_duration_known_count":
                4,

            "completed_planned_duration_s":
                12600,
            "planned_volume_completion_ratio":
                0.875,

            "matched_actual_duration_s":
                13200,
            "actual_vs_total_planned_duration_ratio":
                0.9167,

            "by_priority": {
                "KEY": {
                    "planned": 1,
                    "matched": 1,
                    "planned_duration_s": 7200,
                    "completed_planned_duration_s": 7200,
                    "planned_volume_completion_ratio": 1.0,
                },
                "SUPPORT": {
                    "planned": 2,
                    "matched": 2,
                    "planned_duration_s": 5400,
                    "completed_planned_duration_s": 5400,
                    "planned_volume_completion_ratio": 1.0,
                },
                "EASY": {
                    "planned": 1,
                    "matched": 0,
                    "planned_duration_s": 1800,
                    "completed_planned_duration_s": 0,
                    "planned_volume_completion_ratio": 0.0,
                },
            },
        },

        "schedule": {
            "shifted_session_count":
                2,
            "max_abs_shift_days":
                2,
        },

        "actual_load_window": {
            "session_count":
                4,
            "unplanned_session_count":
                1,
            "duration_s":
                15000,

            "training_load":
                220,
            "training_load_known_count":
                4,

            "work_kj":
                1800,
            "work_kj_known_count":
                3,
        },

        "analysis": {
            "analyzed_session_count":
                3,

            "duration_status_counts": {
                "within": 2,
                "minor": 1,
            },

            "stimulus_status_counts": {
                "aligned": 1,
                "above_target": 1,
                "interval_analysis_required": 1,
            },

            "session_flag_counts": {
                "rpe_above_target": 1,
                "high_leg_fatigue": 1,
            },
        },

        "feedback": {
            "coverage":
                0.75,
            "rpe_avg_descriptive":
                4.7,
            "leg_fatigue_avg_descriptive":
                2.7,
        },

        "actual_sessions": [
            {
                "duration_s": 7200,
                "planned_session_ids": [
                    "key"
                ],
            },
            {
                "duration_s": 3600,
                "planned_session_ids": [
                    "support-1"
                ],
            },
            {
                "duration_s": 2400,
                "planned_session_ids": [
                    "support-2"
                ],
            },
            {
                "duration_s": 1800,
                "planned_session_ids": [],
            },
        ],
    }

    kpis = _build_coach_kpis(
        summary=summary
    )

    assert (
        kpis["schema_version"]
        == "weekly-kpi-v1"
    )

    assert (
        kpis["execution"]["KEY"][
            "session_completion_ratio"
        ]
        == 1.0
    )

    assert (
        kpis["execution"]["EASY"][
            "session_completion_ratio"
        ]
        == 0.0
    )

    assert (
        kpis["load"][
            "actual_week_vs_planned_duration_ratio"
        ]
        == round(
            15000 / 14400,
            4,
        )
    )

    assert (
        kpis["load"][
            "unplanned_duration_s"
        ]
        == 1800
    )

    assert (
        kpis["load"][
            "unplanned_duration_share"
        ]
        == 0.12
    )

    assert (
        kpis["stimulus"][
            "comparable_session_count"
        ]
        == 2
    )

    assert (
        kpis["stimulus"][
            "aligned_ratio"
        ]
        == 0.5
    )

    assert (
        kpis["stimulus"][
            "interval_analysis_required_count"
        ]
        == 1
    )

    assert (
        kpis["duration_execution"][
            "within_ratio"
        ]
        == round(
            2 / 3,
            4,
        )
    )

    assert (
        kpis["subjective_response"][
            "rpe_above_target_count"
        ]
        == 1
    )

    assert (
        kpis["subjective_response"][
            "high_leg_fatigue_count"
        ]
        == 1
    )

    assert (
        kpis["data_readiness"][
            "analysis_coverage"
        ]
        == 0.75
    )

    assert (
        kpis["data_readiness"][
            "work_kj_coverage"
        ]
        == 0.75
    )

    assert (
        kpis["schedule_context"][
            "weekday_shift_penalizes_compliance"
        ]
        is False
    )

    assert (
        kpis["advanced_endurance"][
            "durability"
        ]["status"]
        == "not_available_in_current_analysis"
    )

    assert (
        kpis["advanced_endurance"][
            "decoupling"
        ]["status"]
        == "not_available_in_current_analysis"
    )

    # Distance is deliberately excluded
    # from Coach KPI decision inputs.
    assert (
        "distance"
        not in str(kpis).lower()
    )

    # This layer supplies evidence only.
    assert "decision" not in kpis


def test_rebuilt_weekly_review_contains_coach_kpis():
    db = make_db()

    (
        _,
        athlete,
        week,
    ) = make_week(db)

    plan = add_plan(
        db,
        athlete,
        week,
        name="END",
        sport="cycling",
        priority="KEY",
        day=29,
        duration_s=7200,
    )

    actual = add_actual(
        db,
        athlete,
        fingerprint=
            "weekly-kpi-end",
        sport="Ride",
        start_at=datetime(
            2026,
            9,
            30,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=7200,
        training_load=100,
        work_kj=1200,
        distance_m=50000,
    )

    db.add(
        SessionMatch(
            athlete_id=athlete.id,
            planned_session_id=
                plan.id,
            canonical_session_id=
                actual.id,
            match_method=
                "auto_score",
            match_score=0.95,
            match_evidence={
                "schedule_shifted":
                    True,
                "day_shift": 1,
            },
        )
    )

    db.add(
        SessionAnalysis(
            athlete_id=athlete.id,
            canonical_session_id=
                actual.id,
            planned_session_id=
                plan.id,
            analysis_version=
                "deterministic-v6",
            classification=
                "matched",
            evidence={
                "duration_assessment": {
                    "status": "within",
                },
                "stimulus_assessment": {
                    "status": "aligned",
                },
                "subjective_response": {
                    "status": "available",
                },
            },
            flags=[],
        )
    )

    db.add(
        SessionFeedback(
            athlete_id=athlete.id,
            canonical_session_id=
                actual.id,
            rpe=3,
            leg_fatigue=2,
            comment="Good",
            custom_metrics={},
        )
    )

    db.commit()

    review = WeeklyReviewService(
        db
    ).rebuild(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    kpis = review["summary"][
        "coach_kpis"
    ]

    assert (
        review["review_version"]
        == "deterministic-weekly-v2"
    )

    assert (
        kpis["execution"]["KEY"][
            "session_completion_ratio"
        ]
        == 1.0
    )

    assert (
        kpis["execution"][
            "planned_volume_completion_ratio"
        ]
        == 1.0
    )

    assert (
        kpis["load"][
            "actual_week_vs_planned_duration_ratio"
        ]
        == 1.0
    )

    assert (
        kpis["stimulus"][
            "aligned_ratio"
        ]
        == 1.0
    )

    assert (
        kpis["data_readiness"][
            "analysis_coverage"
        ]
        == 1.0
    )

    assert (
        kpis["schedule_context"][
            "shifted_session_count"
        ]
        == 1
    )

from copy import deepcopy
from datetime import (
    date,
    datetime,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CoachDecision,
    Macrocycle,
    Season,
    TrainingWeek,
    User,
    WeeklyReview,
)
from app.services.coach_decision_service import (
    CoachDecisionService,
)


def make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    return Session(engine)


def good_kpis() -> dict:
    return {
        "schema_version":
            "weekly-kpi-v1",

        "period_status":
            "complete",

        "execution": {
            "session_completion_ratio":
                1.0,

            "planned_volume_completion_ratio":
                1.0,

            "matched_actual_vs_planned_duration_ratio":
                1.0,

            "KEY": {
                "planned_session_count":
                    2,
                "matched_session_count":
                    2,
                "session_completion_ratio":
                    1.0,
                "planned_volume_completion_ratio":
                    1.0,
            },

            "SUPPORT": {
                "planned_session_count":
                    2,
                "matched_session_count":
                    2,
                "session_completion_ratio":
                    1.0,
                "planned_volume_completion_ratio":
                    1.0,
            },

            "EASY": {
                "planned_session_count":
                    1,
                "matched_session_count":
                    1,
                "session_completion_ratio":
                    1.0,
                "planned_volume_completion_ratio":
                    1.0,
            },
        },

        "load": {
            "planned_duration_s":
                36000,
            "actual_week_duration_s":
                36000,
            "actual_week_vs_planned_duration_ratio":
                1.0,
            "training_load":
                420,
            "work_kj":
                5200,
            "unplanned_session_count":
                0,
            "unplanned_duration_s":
                0,
            "unplanned_duration_share":
                0.0,
        },

        "stimulus": {
            "comparable_session_count":
                3,
            "aligned_count":
                3,
            "above_target_count":
                0,
            "below_target_count":
                0,
            "mixed_count":
                0,
            "aligned_ratio":
                1.0,
            "deviation_ratio":
                0.0,
            "interval_analysis_required_count":
                1,
            "not_evaluable_count":
                1,
        },

        "duration_execution": {
            "comparable_session_count":
                4,
            "within_count":
                4,
            "minor_deviation_count":
                0,
            "major_deviation_count":
                0,
            "within_ratio":
                1.0,
            "major_deviation_ratio":
                0.0,
        },

        "subjective_response": {
            "feedback_coverage":
                0.8,
            "rpe_above_target_count":
                0,
            "rpe_below_target_count":
                0,
            "high_leg_fatigue_count":
                0,
            "rpe_avg_descriptive":
                4.0,
            "leg_fatigue_avg_descriptive":
                2.0,
        },

        "data_readiness": {
            "analysis_coverage":
                1.0,
            "feedback_coverage":
                0.8,
            "planned_duration_coverage":
                1.0,
            "training_load_coverage":
                1.0,
            "work_kj_coverage":
                0.8,
        },

        "schedule_context": {
            "shifted_session_count":
                2,
            "max_abs_shift_days":
                2,
            "weekday_shift_penalizes_compliance":
                False,
        },

        "advanced_endurance": {
            "durability": {
                "status":
                    "not_available_in_current_analysis",
            },
            "decoupling": {
                "status":
                    "not_available_in_current_analysis",
            },
        },
    }


def make_context(
    db: Session,
    *,
    with_review: bool = True,
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
    db.flush()

    review = None

    if with_review:
        review = WeeklyReview(
            athlete_id=athlete.id,
            training_week_id=week.id,
            review_version=
                "deterministic-weekly-v2",
            summary={
                "coach_kpis":
                    good_kpis()
            },
            flags=[],
            generated_at=datetime(
                2026,
                10,
                5,
                8,
                0,
                tzinfo=timezone.utc,
            ),
        )

        db.add(review)

    db.commit()

    return (
        athlete,
        week,
        review,
    )


def test_evaluate_persists_decision():
    db = make_db()

    (
        athlete,
        week,
        review,
    ) = make_context(db)

    result = CoachDecisionService(
        db
    ).evaluate(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert result["status"] == "ready"
    assert result["decision"] == "PROGRESS"
    assert (
        result["decision_version"]
        == "weekly-decision-v1"
    )

    assert (
        result["weekly_review_id"]
        == review.id
    )

    assert len(
        result["input_hash"]
    ) == 64

    rows = list(
        db.scalars(
            select(
                CoachDecision
            )
        )
    )

    assert len(rows) == 1


def test_same_evidence_is_idempotent():
    db = make_db()

    (
        athlete,
        week,
        _,
    ) = make_context(db)

    service = CoachDecisionService(
        db
    )

    first = service.evaluate(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    second = service.evaluate(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert first["id"] == second["id"]

    rows = list(
        db.scalars(
            select(
                CoachDecision
            )
        )
    )

    assert len(rows) == 1


def test_changed_weekly_evidence_creates_history():
    db = make_db()

    (
        athlete,
        week,
        review,
    ) = make_context(db)

    service = CoachDecisionService(
        db
    )

    first = service.evaluate(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert first["decision"] == "PROGRESS"

    changed = deepcopy(
        good_kpis()
    )

    changed["execution"][
        "planned_volume_completion_ratio"
    ] = 0.72

    review.summary = {
        "coach_kpis":
            changed
    }

    review.generated_at = datetime(
        2026,
        10,
        5,
        9,
        0,
        tzinfo=timezone.utc,
    )

    db.commit()

    second = service.evaluate(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert second["decision"] == "HOLD"

    assert (
        second["id"]
        != first["id"]
    )

    history = service.history(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert len(history) == 2

    decisions = {
        item["decision"]
        for item in history
    }

    assert decisions == {
        "PROGRESS",
        "HOLD",
    }


def test_latest_returns_most_recent_decision():
    db = make_db()

    (
        athlete,
        week,
        review,
    ) = make_context(db)

    service = CoachDecisionService(
        db
    )

    first = service.evaluate(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    changed = deepcopy(
        good_kpis()
    )

    changed["execution"][
        "planned_volume_completion_ratio"
    ] = 0.72

    review.summary = {
        "coach_kpis":
            changed
    }

    review.generated_at = datetime(
        2026,
        10,
        5,
        9,
        0,
        tzinfo=timezone.utc,
    )

    db.commit()

    second = service.evaluate(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    latest = service.latest(
        athlete_id=athlete.id,
        week_id=week.id,
    )

    assert latest is not None

    assert (
        latest["id"]
        == second["id"]
    )

    assert (
        latest["id"]
        != first["id"]
    )


def test_missing_weekly_review_is_rejected():
    db = make_db()

    (
        athlete,
        week,
        _,
    ) = make_context(
        db,
        with_review=False,
    )

    with pytest.raises(
        LookupError,
        match="Weekly review not generated",
    ):
        CoachDecisionService(
            db
        ).evaluate(
            athlete_id=athlete.id,
            week_id=week.id,
        )

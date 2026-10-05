from datetime import (
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
    CanonicalSession,
    SessionFeedback,
    User,
)
from app.schemas.session_feedback import (
    SessionFeedbackUpdate,
)
from app.services.session_feedback_service import (
    SessionFeedbackService,
)
from app.services.session_query_service import (
    SessionQueryService,
)


def make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    return Session(engine)


def make_fixture(
    db: Session,
):
    user = User(
        timezone="Europe/Warsaw"
    )

    other_user = User(
        timezone="Europe/Warsaw"
    )

    db.add_all(
        [
            user,
            other_user,
        ]
    )

    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Athlete",
    )

    other_athlete = Athlete(
        user_id=other_user.id,
        display_name="Other Athlete",
    )

    db.add_all(
        [
            athlete,
            other_athlete,
        ]
    )

    db.flush()

    session = CanonicalSession(
        athlete_id=athlete.id,
        sport="cycling",
        indoor=False,
        start_at=datetime(
            2026,
            10,
            5,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=7200,
        fingerprint="feedback-test",
    )

    db.add(session)
    db.commit()

    db.refresh(athlete)
    db.refresh(other_athlete)
    db.refresh(session)

    return (
        athlete,
        other_athlete,
        session,
    )


def test_create_core_session_feedback():
    db = make_db()

    (
        athlete,
        _,
        session,
    ) = make_fixture(db)

    feedback = (
        SessionFeedbackService(
            db
        ).update(
            athlete_id=athlete.id,
            session_id=session.id,
            payload=SessionFeedbackUpdate(
                rpe=4,
                leg_fatigue=2,
                comment=(
                    "Steady endurance ride"
                ),
            ),
        )
    )

    assert feedback["rpe"] == 4
    assert (
        feedback["leg_fatigue"]
        == 2
    )

    assert (
        feedback["comment"]
        == "Steady endurance ride"
    )

    assert (
        feedback["custom_metrics"]
        == {}
    )


def test_patch_preserves_unmodified_feedback_fields():
    db = make_db()

    (
        athlete,
        _,
        session,
    ) = make_fixture(db)

    service = (
        SessionFeedbackService(
            db
        )
    )

    first = service.update(
        athlete_id=athlete.id,
        session_id=session.id,
        payload=SessionFeedbackUpdate(
            rpe=4,
            leg_fatigue=2,
            custom_metrics={
                "asymmetry": {
                    "side": "right",
                    "severity": 3.0,
                }
            },
        ),
    )

    second = service.update(
        athlete_id=athlete.id,
        session_id=session.id,
        payload=SessionFeedbackUpdate(
            rpe=5,
        ),
    )

    rows = list(
        db.scalars(
            select(
                SessionFeedback
            )
        )
    )

    assert (
        first["id"]
        == second["id"]
    )

    assert second["rpe"] == 5

    assert (
        second["leg_fatigue"]
        == 2
    )

    assert (
        second["custom_metrics"]
        == {
            "asymmetry": {
                "side": "right",
                "severity": 3.0,
            }
        }
    )

    assert len(rows) == 1


def test_session_detail_contains_feedback():
    db = make_db()

    (
        athlete,
        _,
        session,
    ) = make_fixture(db)

    SessionFeedbackService(
        db
    ).update(
        athlete_id=athlete.id,
        session_id=session.id,
        payload=SessionFeedbackUpdate(
            rpe=3.5,
            leg_fatigue=1.5,
        ),
    )

    detail = (
        SessionQueryService(
            db
        ).get_session(
            athlete_id=athlete.id,
            session_id=session.id,
        )
    )

    assert detail is not None

    assert (
        detail["feedback"]["rpe"]
        == 3.5
    )

    assert (
        detail[
            "feedback"
        ]["leg_fatigue"]
        == 1.5
    )


def test_feedback_requires_session_ownership():
    db = make_db()

    (
        _,
        other_athlete,
        session,
    ) = make_fixture(db)

    with pytest.raises(
        LookupError,
        match="Session not found",
    ):
        SessionFeedbackService(
            db
        ).update(
            athlete_id=
                other_athlete.id,
            session_id=session.id,
            payload=
                SessionFeedbackUpdate(
                    rpe=4,
                ),
        )


def test_empty_new_feedback_is_rejected():
    db = make_db()

    (
        athlete,
        _,
        session,
    ) = make_fixture(db)

    with pytest.raises(
        ValueError,
        match="empty feedback",
    ):
        SessionFeedbackService(
            db
        ).update(
            athlete_id=athlete.id,
            session_id=session.id,
            payload=
                SessionFeedbackUpdate(
                    rpe=None,
                ),
        )

    rows = list(
        db.scalars(
            select(
                SessionFeedback
            )
        )
    )

    assert rows == []

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CanonicalSession,
    CanonicalSessionSource,
    SessionMetricSource,
    SourceActivity,
    User,
)
from app.services.session_query_service import SessionQueryService


def make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def make_fixture(db: Session):
    user = User(timezone="Europe/Warsaw")
    db.add(user)
    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Test Athlete",
    )
    db.add(athlete)
    db.flush()

    start = datetime(2026, 9, 22, 16, 0, tzinfo=timezone.utc)

    canonical = CanonicalSession(
        athlete_id=athlete.id,
        sport="Ride",
        indoor=True,
        start_at=start,
        duration_s=3600,
        distance_m=40000,
        avg_power_w=210,
        normalized_power_w=220,
        avg_hr_bpm=150,
        duplicate_status="merged",
        analysis_level="basic",
        fingerprint="test-fingerprint",
    )
    db.add(canonical)
    db.flush()

    garmin = SourceActivity(
        athlete_id=athlete.id,
        provider="intervals",
        provider_activity_id="garmin-001",
        recording_source="GARMIN_CONNECT",
        name="Garmin recording",
        sport="Ride",
        indoor=True,
        start_at=start,
        duration_s=3600,
        avg_power_w=210,
        avg_hr_bpm=150,
        raw_payload={},
        payload_hash="garmin-hash",
    )

    mywhoosh = SourceActivity(
        athlete_id=athlete.id,
        provider="intervals",
        provider_activity_id="mywhoosh-001",
        recording_source="OAUTH_CLIENT",
        name="MyWhoosh recording",
        sport="Ride",
        indoor=True,
        start_at=start,
        duration_s=3600,
        distance_m=40000,
        raw_payload={},
        payload_hash="mywhoosh-hash",
    )

    db.add_all([garmin, mywhoosh])
    db.flush()

    db.add_all(
        [
            CanonicalSessionSource(
                canonical_session_id=canonical.id,
                source_activity_id=garmin.id,
                role="PRIMARY",
                duplicate_score=None,
                manual_override=False,
            ),
            CanonicalSessionSource(
                canonical_session_id=canonical.id,
                source_activity_id=mywhoosh.id,
                role="SUPPLEMENTAL",
                duplicate_score=0.99,
                manual_override=False,
            ),
        ]
    )

    db.add_all(
        [
            SessionMetricSource(
                canonical_session_id=canonical.id,
                metric_name="avg_hr_bpm",
                value_numeric=150,
                value_text=None,
                unit="bpm",
                source_activity_id=garmin.id,
                quality_score=0.95,
                selection_reason="physiology source",
            ),
            SessionMetricSource(
                canonical_session_id=canonical.id,
                metric_name="distance_m",
                value_numeric=40000,
                value_text=None,
                unit="m",
                source_activity_id=mywhoosh.id,
                quality_score=0.90,
                selection_reason="route source",
            ),
        ]
    )

    db.commit()

    return athlete, canonical


def test_list_sessions_returns_canonical_summary():
    db = make_db()
    athlete, canonical = make_fixture(db)

    items = SessionQueryService(db).list_sessions(
        athlete_id=athlete.id,
        limit=10,
    )

    assert len(items) == 1
    assert items[0]["id"] == canonical.id
    assert items[0]["duplicate_status"] == "merged"
    assert items[0]["avg_power_w"] == 210
    assert items[0]["distance_m"] == 40000


def test_session_detail_exposes_source_and_metric_provenance():
    db = make_db()
    athlete, canonical = make_fixture(db)

    detail = SessionQueryService(db).get_session(
        athlete_id=athlete.id,
        session_id=canonical.id,
    )

    assert detail is not None

    sources = {
        item["provider_activity_id"]: item
        for item in detail["sources"]
    }

    assert sources["garmin-001"]["role"] == "PRIMARY"
    assert sources["mywhoosh-001"]["role"] == "SUPPLEMENTAL"

    metric_sources = {
        item["metric_name"]: item
        for item in detail["metric_sources"]
    }

    assert (
        metric_sources["avg_hr_bpm"]["provider_activity_id"]
        == "garmin-001"
    )
    assert (
        metric_sources["distance_m"]["provider_activity_id"]
        == "mywhoosh-001"
    )


def test_session_detail_is_scoped_to_athlete():
    db = make_db()
    athlete, canonical = make_fixture(db)

    other_user = User(timezone="Europe/Warsaw")
    db.add(other_user)
    db.flush()

    other_athlete = Athlete(
        user_id=other_user.id,
        display_name="Other Athlete",
    )
    db.add(other_athlete)
    db.commit()

    detail = SessionQueryService(db).get_session(
        athlete_id=other_athlete.id,
        session_id=canonical.id,
    )

    assert detail is None

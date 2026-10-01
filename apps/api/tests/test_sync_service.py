import json
from pathlib import Path

import pytest

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CanonicalSession,
    CanonicalSessionSource,
    SessionMetricSource,
    SourceActivity,
    SyncState,
    User,
)
import app.services.sync_service as sync_module
from app.services.sync_service import IntervalsSyncService

FIX = Path(__file__).parent / "fixtures"


def payload(name):
    return json.loads((FIX / name).read_text())


class FakeIntervalsClient:
    batches = []

    def __init__(self, *args, **kwargs):
        pass

    def list_activities(self, oldest, newest):
        return self.batches.pop(0)



class FailingIntervalsClient:
    def __init__(self, *args, **kwargs):
        pass

    def list_activities(self, oldest, newest):
        raise RuntimeError("Intervals unavailable")


def make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return Session(engine)


def make_athlete(db: Session):
    user = User(timezone="Europe/Warsaw")
    db.add(user)
    db.flush()
    athlete = Athlete(user_id=user.id, display_name="Test")
    db.add(athlete)
    db.commit()
    return athlete


def test_late_duplicate_rebuilds_one_canonical_session(monkeypatch):
    db = make_db()
    athlete = make_athlete(db)
    monkeypatch.setattr(sync_module, "IntervalsClient", FakeIntervalsClient)

    # First sync sees only Garmin.
    FakeIntervalsClient.batches = [[payload("garmin.json")], [payload("garmin.json"), payload("mywhoosh.json")]]
    first = IntervalsSyncService(db).sync(athlete.id, days=7)
    assert first["source_activities"] == 1
    first_canonical = db.scalar(select(CanonicalSession))
    assert first_canonical.duplicate_status == "single"
    first_canonical_id = first_canonical.id

    # Second sync sees the same physical workout from two recording sources.
    second = IntervalsSyncService(db).sync(athlete.id, days=7)
    assert second["source_activities"] == 2
    canonicals = list(db.scalars(select(CanonicalSession)))
    assert len(canonicals) == 1
    assert canonicals[0].id == first_canonical_id
    assert canonicals[0].duplicate_status == "merged"
    assert len(list(db.scalars(select(SourceActivity)))) == 2

    metrics = list(db.scalars(select(SessionMetricSource)))
    sources_by_metric = {}
    for metric in metrics:
        source = db.get(SourceActivity, metric.source_activity_id)
        sources_by_metric[metric.metric_name] = source.provider_activity_id

    assert sources_by_metric["avg_hr_bpm"] == "garmin-001"
    assert sources_by_metric["distance_m"] == "mywhoosh-001"


def test_repeated_sync_is_idempotent_and_preserves_canonical_identity(monkeypatch):
    db = make_db()
    athlete = make_athlete(db)
    monkeypatch.setattr(sync_module, "IntervalsClient", FakeIntervalsClient)

    batch = [payload("garmin.json"), payload("mywhoosh.json")]
    FakeIntervalsClient.batches = [batch, batch]

    first = IntervalsSyncService(db).sync(athlete.id, days=7)
    assert first["source_activities"] == 2

    canonicals = list(db.scalars(select(CanonicalSession)))
    assert len(canonicals) == 1
    canonical_id = canonicals[0].id

    source_count = len(list(db.scalars(select(SourceActivity))))
    link_count = len(list(db.scalars(select(CanonicalSessionSource))))
    metric_count = len(list(db.scalars(select(SessionMetricSource))))

    second = IntervalsSyncService(db).sync(athlete.id, days=7)
    assert second["source_activities"] == 2

    canonicals = list(db.scalars(select(CanonicalSession)))
    assert len(canonicals) == 1
    assert canonicals[0].id == canonical_id

    assert len(list(db.scalars(select(SourceActivity)))) == source_count == 2
    assert len(list(db.scalars(select(CanonicalSessionSource)))) == link_count == 2
    assert len(list(db.scalars(select(SessionMetricSource)))) == metric_count
    assert metric_count > 0



def test_sync_state_records_success_and_failure(monkeypatch):
    db = make_db()
    athlete = make_athlete(db)

    monkeypatch.setattr(sync_module, "IntervalsClient", FakeIntervalsClient)
    FakeIntervalsClient.batches = [[payload("garmin.json")]]

    result = IntervalsSyncService(db).sync(athlete.id, days=7)

    state = db.scalar(
        select(SyncState).where(
            SyncState.athlete_id == athlete.id,
            SyncState.resource == "intervals.activities",
        )
    )

    assert state is not None
    assert state.status == "idle"
    assert state.last_successful_sync is not None
    assert result["sync_state"]["status"] == "idle"

    monkeypatch.setattr(sync_module, "IntervalsClient", FailingIntervalsClient)

    with pytest.raises(RuntimeError, match="Intervals unavailable"):
        IntervalsSyncService(db).sync(athlete.id, days=7)

    db.expire_all()

    state = db.scalar(
        select(SyncState).where(
            SyncState.athlete_id == athlete.id,
            SyncState.resource == "intervals.activities",
        )
    )

    assert state.status == "error"
    assert state.last_successful_sync is not None
    assert len(list(db.scalars(select(SyncState)))) == 1


def test_source_correction_preserves_identity_when_fingerprint_changes(
    monkeypatch,
):
    db = make_db()
    athlete = make_athlete(db)

    monkeypatch.setattr(
        sync_module,
        "IntervalsClient",
        FakeIntervalsClient,
    )

    original = payload("garmin.json")
    corrected = payload("garmin.json")

    # Same provider activity, but Intervals later corrects values enough
    # to move the session into another fingerprint bucket.
    corrected["start_date"] = "2026-09-28T16:06:00Z"
    corrected["moving_time"] = 4500

    FakeIntervalsClient.batches = [
        [original],
        [corrected],
    ]

    IntervalsSyncService(db).sync(
        athlete.id,
        days=7,
    )

    first = db.scalar(
        select(CanonicalSession)
    )

    first_id = first.id
    first_fingerprint = first.fingerprint

    IntervalsSyncService(db).sync(
        athlete.id,
        days=7,
    )

    canonicals = list(
        db.scalars(
            select(CanonicalSession)
        )
    )

    assert len(canonicals) == 1

    corrected_canonical = canonicals[0]

    assert corrected_canonical.id == first_id
    assert corrected_canonical.fingerprint != first_fingerprint

    links = list(
        db.scalars(
            select(CanonicalSessionSource)
        )
    )

    assert len(links) == 1
    assert links[0].canonical_session_id == first_id


def test_two_existing_canonicals_can_collapse_into_one_stable_session(
    monkeypatch,
):
    db = make_db()
    athlete = make_athlete(db)

    monkeypatch.setattr(
        sync_module,
        "IntervalsClient",
        FakeIntervalsClient,
    )

    garmin = payload("garmin.json")

    mywhoosh_separate = payload("mywhoosh.json")
    mywhoosh_separate["start_date"] = (
        "2026-09-28T17:00:25Z"
    )

    mywhoosh_corrected = payload("mywhoosh.json")

    FakeIntervalsClient.batches = [
        [
            garmin,
            mywhoosh_separate,
        ],
        [
            garmin,
            mywhoosh_corrected,
        ],
    ]

    IntervalsSyncService(db).sync(
        athlete.id,
        days=7,
    )

    first_canonicals = list(
        db.scalars(
            select(CanonicalSession)
        )
    )

    assert len(first_canonicals) == 2

    previous_ids = {
        canonical.id
        for canonical in first_canonicals
    }

    IntervalsSyncService(db).sync(
        athlete.id,
        days=7,
    )

    final_canonicals = list(
        db.scalars(
            select(CanonicalSession)
        )
    )

    assert len(final_canonicals) == 1
    assert final_canonicals[0].id in previous_ids
    assert final_canonicals[0].duplicate_status == "merged"

    links = list(
        db.scalars(
            select(CanonicalSessionSource)
        )
    )

    assert len(links) == 2

    assert {
        link.canonical_session_id
        for link in links
    } == {
        final_canonicals[0].id
    }


def test_previously_merged_session_can_split_without_losing_source(
    monkeypatch,
):
    db = make_db()
    athlete = make_athlete(db)

    monkeypatch.setattr(
        sync_module,
        "IntervalsClient",
        FakeIntervalsClient,
    )

    garmin = payload("garmin.json")
    mywhoosh = payload("mywhoosh.json")

    mywhoosh_separate = payload("mywhoosh.json")
    mywhoosh_separate["start_date"] = (
        "2026-09-28T17:00:25Z"
    )

    # First sync: both recordings describe one physical session.
    # Second sync: Intervals correction shows that MyWhoosh actually
    # belongs to a separate session.
    #
    # Put MyWhoosh first deliberately: source ordering must not decide
    # which physical session keeps the previous canonical identity.
    FakeIntervalsClient.batches = [
        [
            garmin,
            mywhoosh,
        ],
        [
            mywhoosh_separate,
            garmin,
        ],
    ]

    IntervalsSyncService(db).sync(
        athlete.id,
        days=7,
    )

    first_canonicals = list(
        db.scalars(
            select(CanonicalSession)
        )
    )

    assert len(first_canonicals) == 1

    original_canonical_id = first_canonicals[0].id

    first_links = list(
        db.scalars(
            select(CanonicalSessionSource)
        )
    )

    assert len(first_links) == 2

    IntervalsSyncService(db).sync(
        athlete.id,
        days=7,
    )

    final_canonicals = list(
        db.scalars(
            select(CanonicalSession)
        )
    )

    assert len(final_canonicals) == 2

    final_ids = {
        canonical.id
        for canonical in final_canonicals
    }

    assert original_canonical_id in final_ids

    sources = {
        source.provider_activity_id: source
        for source in db.scalars(
            select(SourceActivity)
        )
    }

    links = list(
        db.scalars(
            select(CanonicalSessionSource)
        )
    )

    assert len(links) == 2

    source_ids_in_links = [
        link.source_activity_id
        for link in links
    ]

    assert len(set(source_ids_in_links)) == 2

    garmin_link = next(
        link
        for link in links
        if link.source_activity_id
        == sources["garmin-001"].id
    )

    mywhoosh_link = next(
        link
        for link in links
        if link.source_activity_id
        == sources["mywhoosh-001"].id
    )

    # Garmin was the PRIMARY source of the previously merged session,
    # so that physical session retains the old stable UUID.
    assert (
        garmin_link.canonical_session_id
        == original_canonical_id
    )

    assert (
        mywhoosh_link.canonical_session_id
        != original_canonical_id
    )

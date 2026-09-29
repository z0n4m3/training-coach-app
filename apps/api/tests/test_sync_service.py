import json
from pathlib import Path

from sqlalchemy import create_engine, event, select
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

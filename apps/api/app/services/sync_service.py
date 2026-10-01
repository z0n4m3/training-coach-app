from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.clients.intervals import IntervalsClient
from app.core.config import settings
from app.models.entities import (
    Athlete,
    CanonicalSession,
    CanonicalSessionSource,
    SessionMetricSource,
    SourceActivity,
    SyncState,
)
from app.services.canonicalizer import canonicalize
from app.services.duplicate_engine import build_groups, score_duplicate
from app.services.intervals_mapper import from_intervals


INTERVALS_ACTIVITIES_RESOURCE = "intervals.activities"


class IntervalsSyncService:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_sync_state(self, athlete_id: uuid.UUID) -> SyncState:
        state = self.db.scalar(
            select(SyncState).where(
                SyncState.athlete_id == athlete_id,
                SyncState.resource == INTERVALS_ACTIVITIES_RESOURCE,
            )
        )
        if state is None:
            state = SyncState(
                athlete_id=athlete_id,
                resource=INTERVALS_ACTIVITIES_RESOURCE,
                status="idle",
            )
            self.db.add(state)
            self.db.flush()
        return state

    def sync(self, athlete_id: uuid.UUID, days: int = 7, source_preference: str = "auto") -> dict:
        athlete = self.db.get(Athlete, athlete_id)
        if athlete is None:
            raise ValueError("Unknown athlete_id")

        newest = date.today()
        oldest = newest - timedelta(days=max(1, min(days, 31)))

        state = self._get_or_create_sync_state(athlete_id)
        state.status = "running"
        self.db.commit()

        try:
            result = self._sync_window(
                athlete_id=athlete_id,
                oldest=oldest,
                newest=newest,
                source_preference=source_preference,
            )
        except Exception:
            self.db.rollback()
            state = self._get_or_create_sync_state(athlete_id)
            state.status = "error"
            self.db.commit()
            raise

        completed_at = datetime.now(timezone.utc)
        state = self._get_or_create_sync_state(athlete_id)
        state.status = "idle"
        state.last_successful_sync = completed_at
        self.db.commit()

        result["sync_state"] = {
            "status": state.status,
            "last_successful_sync": completed_at.isoformat(),
        }
        return result

    def _sync_window(
        self,
        athlete_id: uuid.UUID,
        oldest: date,
        newest: date,
        source_preference: str,
    ) -> dict:
        client = IntervalsClient(settings.intervals_base_url, settings.intervals_api_key, settings.intervals_athlete_id)
        raw = client.list_activities(oldest, newest)
        snapshots = [from_intervals(item) for item in raw]

        source_rows: list[SourceActivity] = []
        for snapshot in snapshots:
            row = self.db.scalar(
                select(SourceActivity).where(
                    SourceActivity.athlete_id == athlete_id,
                    SourceActivity.provider == "intervals",
                    SourceActivity.provider_activity_id == snapshot.provider_activity_id,
                )
            )
            if row is None:
                row = SourceActivity(
                    athlete_id=athlete_id,
                    provider="intervals",
                    provider_activity_id=snapshot.provider_activity_id,
                    raw_payload=snapshot.raw_payload or {},
                    payload_hash=snapshot.payload_hash,
                    sport=snapshot.sport,
                    start_at=snapshot.start_at,
                )
                self.db.add(row)
            for field in (
                "recording_source", "name", "sport", "indoor", "start_at", "end_at", "duration_s", "distance_m",
                "elevation_m", "avg_power_w", "normalized_power_w", "avg_hr_bpm", "max_hr_bpm",
                "avg_cadence_rpm", "work_kj", "training_load", "paired_event_id",
            ):
                setattr(row, field, getattr(snapshot, field))
            row.raw_payload = snapshot.raw_payload or {}
            row.payload_hash = snapshot.payload_hash
            source_rows.append(row)

        self.db.flush()

        # Remember canonical sessions touched by this sync, but do not delete them up
        # front. Stable CanonicalSession IDs are important because later feedback,
        # analyses and plan/execution links will reference them.
        source_ids = [row.id for row in source_rows]
        affected_canonical_ids: set[uuid.UUID] = set()
        if source_ids:
            affected_canonical_ids = set(
                self.db.scalars(
                    select(CanonicalSessionSource.canonical_session_id).where(
                        CanonicalSessionSource.source_activity_id.in_(source_ids)
                    )
                )
            )

        groups = build_groups(snapshots, settings.duplicate_auto_merge_threshold)
        canonical_count = 0
        merged_count = 0
        rebuilt_canonical_ids: set[uuid.UUID] = set()

        for indexes in groups:
            group_snapshots = [snapshots[i] for i in indexes]
            result = canonicalize(group_snapshots, source_preference)
            canonical = self.db.scalar(
                select(CanonicalSession).where(
                    CanonicalSession.athlete_id == athlete_id,
                    CanonicalSession.fingerprint == result.fingerprint,
                )
            )
            if canonical is None:
                canonical = CanonicalSession(
                    athlete_id=athlete_id,
                    fingerprint=result.fingerprint,
                    sport=result.sport,
                    start_at=result.start_at,
                    duplicate_status=result.duplicate_status,
                )
                self.db.add(canonical)
                self.db.flush()

            canonical.sport = result.sport
            canonical.indoor = result.indoor
            canonical.start_at = result.start_at
            canonical.end_at = result.end_at
            canonical.duplicate_status = result.duplicate_status
            for metric, value in result.values.items():
                setattr(canonical, metric, value)

            rebuilt_canonical_ids.add(canonical.id)

            self.db.execute(delete(CanonicalSessionSource).where(CanonicalSessionSource.canonical_session_id == canonical.id))
            self.db.execute(delete(SessionMetricSource).where(SessionMetricSource.canonical_session_id == canonical.id))

            row_by_provider_id = {row.provider_activity_id: row for row in source_rows}
            primary_id = result.primary_provider_activity_id
            for snap in group_snapshots:
                row = row_by_provider_id[snap.provider_activity_id]
                duplicate_score = None
                if snap.provider_activity_id != primary_id:
                    primary_snap = next(x for x in group_snapshots if x.provider_activity_id == primary_id)
                    duplicate_score = score_duplicate(primary_snap, snap).total
                self.db.add(
                    CanonicalSessionSource(
                        canonical_session_id=canonical.id,
                        source_activity_id=row.id,
                        role="PRIMARY" if snap.provider_activity_id == primary_id else "SUPPLEMENTAL",
                        duplicate_score=duplicate_score,
                        manual_override=False,
                    )
                )

            for choice in result.metrics:
                row = row_by_provider_id[choice.source_provider_activity_id]
                self.db.add(
                    SessionMetricSource(
                        canonical_session_id=canonical.id,
                        metric_name=choice.metric_name,
                        value_numeric=float(choice.value) if isinstance(choice.value, (int, float)) else None,
                        value_text=str(choice.value) if isinstance(choice.value, str) else None,
                        unit=choice.unit,
                        source_activity_id=row.id,
                        quality_score=choice.quality_score,
                        selection_reason=choice.reason,
                    )
                )

            canonical_count += 1
            if len(group_snapshots) > 1:
                merged_count += 1

        # If an activity changed enough to produce a different physical-session
        # fingerprint, remove only the now-obsolete canonical rows. Canonicals whose
        # identity is unchanged keep their original UUID.
        stale_canonical_ids = affected_canonical_ids - rebuilt_canonical_ids
        if stale_canonical_ids:
            self.db.execute(
                delete(CanonicalSession).where(
                    CanonicalSession.id.in_(stale_canonical_ids)
                )
            )

        self.db.commit()
        return {
            "window": {"oldest": oldest.isoformat(), "newest": newest.isoformat()},
            "source_activities": len(snapshots),
            "canonical_sessions": canonical_count,
            "merged_groups": merged_count,
        }

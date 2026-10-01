from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    CanonicalSession,
    CanonicalSessionSource,
    SessionAnalysis,
    SessionMetricSource,
    SourceActivity,
)


class SessionQueryService:
    def __init__(self, db: Session):
        self.db = db

    def list_sessions(
        self,
        athlete_id: uuid.UUID,
        limit: int = 50,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> list[dict]:
        stmt = (
            select(CanonicalSession)
            .where(CanonicalSession.athlete_id == athlete_id)
            .order_by(CanonicalSession.start_at.desc())
            .limit(limit)
        )

        if from_at is not None:
            stmt = stmt.where(CanonicalSession.start_at >= from_at)

        if to_at is not None:
            stmt = stmt.where(CanonicalSession.start_at <= to_at)

        sessions = list(self.db.scalars(stmt))
        return [self._summary(session) for session in sessions]

    def get_session(
        self,
        athlete_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> dict | None:
        session = self.db.scalar(
            select(CanonicalSession).where(
                CanonicalSession.id == session_id,
                CanonicalSession.athlete_id == athlete_id,
            )
        )

        if session is None:
            return None

        source_rows = self.db.execute(
            select(CanonicalSessionSource, SourceActivity)
            .join(
                SourceActivity,
                SourceActivity.id == CanonicalSessionSource.source_activity_id,
            )
            .where(
                CanonicalSessionSource.canonical_session_id == session.id
            )
            .order_by(CanonicalSessionSource.role.asc())
        ).all()

        metric_rows = self.db.execute(
            select(SessionMetricSource, SourceActivity)
            .join(
                SourceActivity,
                SourceActivity.id == SessionMetricSource.source_activity_id,
            )
            .where(
                SessionMetricSource.canonical_session_id == session.id
            )
            .order_by(SessionMetricSource.metric_name.asc())
        ).all()

        analysis = self.db.scalar(
            select(SessionAnalysis).where(
                SessionAnalysis.canonical_session_id
                == session.id,
                SessionAnalysis.athlete_id
                == athlete_id,
            )
        )

        result = self._summary(session)

        result["analysis"] = (
            None
            if analysis is None
            else {
                "id": analysis.id,
                "planned_session_id":
                    analysis.planned_session_id,
                "analysis_version":
                    analysis.analysis_version,
                "classification":
                    analysis.classification,
                "evidence":
                    analysis.evidence,
                "flags":
                    analysis.flags,
                "updated_at":
                    analysis.updated_at,
            }
        )

        result["sources"] = [
            {
                "source_activity_id": source.id,
                "provider": source.provider,
                "provider_activity_id": source.provider_activity_id,
                "recording_source": source.recording_source,
                "name": source.name,
                "role": link.role,
                "duplicate_score": link.duplicate_score,
                "manual_override": link.manual_override,
            }
            for link, source in source_rows
        ]

        result["metric_sources"] = [
            {
                "metric_name": metric.metric_name,
                "value_numeric": metric.value_numeric,
                "value_text": metric.value_text,
                "unit": metric.unit,
                "quality_score": metric.quality_score,
                "selection_reason": metric.selection_reason,
                "source_activity_id": source.id,
                "provider_activity_id": source.provider_activity_id,
                "recording_source": source.recording_source,
            }
            for metric, source in metric_rows
        ]

        return result

    @staticmethod
    def _summary(session: CanonicalSession) -> dict:
        return {
            "id": session.id,
            "athlete_id": session.athlete_id,
            "sport": session.sport,
            "indoor": session.indoor,
            "start_at": session.start_at,
            "end_at": session.end_at,
            "duration_s": session.duration_s,
            "distance_m": session.distance_m,
            "elevation_m": session.elevation_m,
            "avg_power_w": session.avg_power_w,
            "normalized_power_w": session.normalized_power_w,
            "avg_hr_bpm": session.avg_hr_bpm,
            "max_hr_bpm": session.max_hr_bpm,
            "avg_cadence_rpm": session.avg_cadence_rpm,
            "work_kj": session.work_kj,
            "training_load": session.training_load,
            "duplicate_status": session.duplicate_status,
            "analysis_level": session.analysis_level,
            "fingerprint": session.fingerprint,
        }

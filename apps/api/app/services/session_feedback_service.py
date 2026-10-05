from __future__ import annotations

import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    CanonicalSession,
    SessionFeedback,
)
from app.schemas.session_feedback import (
    SessionFeedbackUpdate,
)
from app.services.session_analyzer import (
    SessionAnalyzer,
)


class SessionFeedbackService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        *,
        athlete_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> dict | None:
        self._session(
            athlete_id=athlete_id,
            session_id=session_id,
        )

        feedback = self.db.scalar(
            select(
                SessionFeedback
            ).where(
                SessionFeedback
                .athlete_id
                == athlete_id,
                SessionFeedback
                .canonical_session_id
                == session_id,
            )
        )

        if feedback is None:
            return None

        return self._serialize(
            feedback
        )

    def update(
        self,
        *,
        athlete_id: uuid.UUID,
        session_id: uuid.UUID,
        payload: SessionFeedbackUpdate,
    ) -> dict:
        self._session(
            athlete_id=athlete_id,
            session_id=session_id,
        )

        feedback = self.db.scalar(
            select(
                SessionFeedback
            ).where(
                SessionFeedback
                .athlete_id
                == athlete_id,
                SessionFeedback
                .canonical_session_id
                == session_id,
            )
        )

        is_new = feedback is None

        if feedback is None:
            feedback = SessionFeedback(
                athlete_id=athlete_id,
                canonical_session_id=
                    session_id,
                custom_metrics={},
            )

            self.db.add(
                feedback
            )

        fields = payload.model_fields_set

        if "rpe" in fields:
            feedback.rpe = payload.rpe

        if "leg_fatigue" in fields:
            feedback.leg_fatigue = (
                payload.leg_fatigue
            )

        if "comment" in fields:
            feedback.comment = (
                payload.comment
            )

        if "custom_metrics" in fields:
            feedback.custom_metrics = (
                {}
                if payload.custom_metrics
                is None
                else dict(
                    payload.custom_metrics
                )
            )

        if (
            is_new
            and feedback.rpe is None
            and feedback.leg_fatigue
            is None
            and not (
                feedback.comment
                and feedback.comment.strip()
            )
            and not feedback.custom_metrics
        ):
            self.db.rollback()

            raise ValueError(
                "Cannot create empty feedback"
            )

        try:
            self.db.flush()

            SessionAnalyzer(
                self.db
            ).analyze(
                athlete_id,
                {session_id},
            )

            self.db.commit()
            self.db.refresh(
                feedback
            )

        except Exception:
            self.db.rollback()
            raise

        return self._serialize(
            feedback
        )

    def _session(
        self,
        *,
        athlete_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> CanonicalSession:
        session = self.db.scalar(
            select(
                CanonicalSession
            ).where(
                CanonicalSession.id
                == session_id,
                CanonicalSession.athlete_id
                == athlete_id,
            )
        )

        if session is None:
            raise LookupError(
                "Session not found"
            )

        return session

    @staticmethod
    def _aware_utc(
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

    def _serialize(
        self,
        feedback: SessionFeedback,
    ) -> dict:
        return {
            "id":
                feedback.id,
            "athlete_id":
                feedback.athlete_id,
            "canonical_session_id":
                feedback
                .canonical_session_id,
            "rpe":
                feedback.rpe,
            "leg_fatigue":
                feedback.leg_fatigue,
            "comment":
                feedback.comment,
            "custom_metrics":
                feedback.custom_metrics
                or {},
            "created_at":
                self._aware_utc(
                    feedback.created_at
                ),
            "updated_at":
                self._aware_utc(
                    feedback.updated_at
                ),
        }

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.sport import normalize_sport
from app.models.entities import (
    CanonicalSession,
    TrainingSetup,
)
from app.services.session_analyzer import (
    SessionAnalyzer,
)
from app.services.session_query_service import (
    SessionQueryService,
)


class SessionContextService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def set_training_setup(
        self,
        *,
        athlete_id: uuid.UUID,
        session_id: uuid.UUID,
        training_setup_id:
            uuid.UUID | None,
    ) -> dict:
        session = self.db.scalar(
            select(CanonicalSession).where(
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

        if training_setup_id is None:
            session.training_setup_id = None

        else:
            setup = self.db.scalar(
                select(TrainingSetup).where(
                    TrainingSetup.id
                    == training_setup_id,
                    TrainingSetup.athlete_id
                    == athlete_id,
                )
            )

            if setup is None:
                raise LookupError(
                    "Training setup not found"
                )

            if not setup.active:
                raise ValueError(
                    "Training setup is inactive"
                )

            if (
                normalize_sport(
                    session.sport
                )
                != setup.sport
            ):
                raise ValueError(
                    (
                        "Training setup sport "
                        "does not match session sport"
                    )
                )

            session.training_setup_id = (
                setup.id
            )

        self.db.flush()

        SessionAnalyzer(
            self.db
        ).analyze(
            athlete_id,
            {session.id},
        )

        self.db.commit()

        result = SessionQueryService(
            self.db
        ).get_session(
            athlete_id=athlete_id,
            session_id=session.id,
        )

        if result is None:
            raise LookupError(
                "Session not found"
            )

        return result

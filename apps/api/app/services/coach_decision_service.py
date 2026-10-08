from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import (
    select,
)
from sqlalchemy.orm import Session

from app.models.entities import (
    Athlete,
    CoachDecision,
    TrainingWeek,
    WeeklyReview,
    utcnow,
)
from app.services.coach_decision_policy import (
    DECISION_VERSION,
    evaluate_weekly_decision,
)


class CoachDecisionService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    @staticmethod
    def _input_hash(
        coach_kpis: dict,
    ) -> str:
        canonical = json.dumps(
            coach_kpis,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()

    def evaluate(
        self,
        *,
        athlete_id: uuid.UUID,
        week_id: uuid.UUID,
    ) -> dict:
        self._owned_week(
            athlete_id=athlete_id,
            week_id=week_id,
        )

        review = self.db.scalar(
            select(
                WeeklyReview
            ).where(
                WeeklyReview.athlete_id
                == athlete_id,
                WeeklyReview.training_week_id
                == week_id,
            )
        )

        if review is None:
            raise LookupError(
                "Weekly review not generated"
            )

        summary = (
            review.summary
            or {}
        )

        coach_kpis = summary.get(
            "coach_kpis"
        )

        if not isinstance(
            coach_kpis,
            dict,
        ):
            raise ValueError(
                "Weekly review has no coach KPIs"
            )

        input_hash = self._input_hash(
            coach_kpis
        )

        existing = self.db.scalar(
            select(
                CoachDecision
            ).where(
                CoachDecision.athlete_id
                == athlete_id,
                CoachDecision.training_week_id
                == week_id,
                CoachDecision.decision_version
                == DECISION_VERSION,
                CoachDecision.input_hash
                == input_hash,
            )
        )

        if existing is not None:
            return self._serialize(
                existing
            )

        result = (
            evaluate_weekly_decision(
                coach_kpis
            )
        )

        row = CoachDecision(
            athlete_id=athlete_id,
            training_week_id=week_id,
            weekly_review_id=
                review.id,

            decision_version=
                result[
                    "decision_version"
                ],

            input_hash=input_hash,

            status=
                result["status"],

            decision=
                result["decision"],

            confidence=
                result["confidence"],

            selected_rule=
                result[
                    "selected_rule"
                ],

            reasons=
                result[
                    "reasons"
                ],

            evidence=
                result[
                    "evidence"
                ],

            constraints=
                result[
                    "constraints"
                ],

            source_review_version=
                review.review_version,

            source_review_generated_at=
                review.generated_at,

            generated_at=utcnow(),
        )

        self.db.add(
            row
        )
        self.db.commit()
        self.db.refresh(
            row
        )

        return self._serialize(
            row
        )

    def latest(
        self,
        *,
        athlete_id: uuid.UUID,
        week_id: uuid.UUID,
    ) -> dict | None:
        self._owned_week(
            athlete_id=athlete_id,
            week_id=week_id,
        )

        row = self.db.scalar(
            select(
                CoachDecision
            )
            .where(
                CoachDecision.athlete_id
                == athlete_id,
                CoachDecision.training_week_id
                == week_id,
            )
            .order_by(
                CoachDecision.generated_at
                .desc(),
                CoachDecision.created_at
                .desc(),
            )
        )

        if row is None:
            return None

        return self._serialize(
            row
        )

    def history(
        self,
        *,
        athlete_id: uuid.UUID,
        week_id: uuid.UUID,
    ) -> list[dict]:
        self._owned_week(
            athlete_id=athlete_id,
            week_id=week_id,
        )

        rows = list(
            self.db.scalars(
                select(
                    CoachDecision
                )
                .where(
                    CoachDecision.athlete_id
                    == athlete_id,
                    CoachDecision.training_week_id
                    == week_id,
                )
                .order_by(
                    CoachDecision.generated_at
                    .desc(),
                    CoachDecision.created_at
                    .desc(),
                )
            )
        )

        return [
            self._serialize(
                row
            )
            for row in rows
        ]

    def _owned_week(
        self,
        *,
        athlete_id: uuid.UUID,
        week_id: uuid.UUID,
    ) -> TrainingWeek:
        athlete = self.db.get(
            Athlete,
            athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
            )

        week = self.db.scalar(
            select(
                TrainingWeek
            ).where(
                TrainingWeek.id
                == week_id,
                TrainingWeek.athlete_id
                == athlete_id,
            )
        )

        if week is None:
            raise LookupError(
                "Training week not found"
            )

        return week

    @staticmethod
    def _serialize(
        row: CoachDecision,
    ) -> dict:
        return {
            "id":
                row.id,

            "athlete_id":
                row.athlete_id,

            "training_week_id":
                row.training_week_id,

            "weekly_review_id":
                row.weekly_review_id,

            "decision_version":
                row.decision_version,

            "input_hash":
                row.input_hash,

            "status":
                row.status,

            "decision":
                row.decision,

            "confidence":
                row.confidence,

            "selected_rule":
                row.selected_rule,

            "reasons":
                row.reasons,

            "evidence":
                row.evidence,

            "constraints":
                row.constraints,

            "source_review_version":
                row.source_review_version,

            "source_review_generated_at":
                row.source_review_generated_at,

            "generated_at":
                row.generated_at,

            "created_at":
                row.created_at,
        }

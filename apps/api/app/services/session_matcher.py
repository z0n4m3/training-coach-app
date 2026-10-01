from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.sport import normalize_sport
from app.models.entities import (
    CanonicalSession,
    CanonicalSessionSource,
    PlannedSession,
    SessionMatch,
    SourceActivity,
)


AUTO_MATCH_THRESHOLD = 0.82
AUTO_MATCH_MARGIN = 0.08
MAX_TIME_DELTA_S = 8 * 60 * 60


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SessionMatcher:
    def __init__(self, db: Session):
        self.db = db

    def auto_match(
        self,
        athlete_id: uuid.UUID,
        canonical_ids: set[uuid.UUID],
    ) -> dict:
        result = {
            "matched": 0,
            "matched_by_event_id": 0,
            "matched_by_score": 0,
            "ambiguous": 0,
            "low_confidence": 0,
            "no_candidate": 0,
        }

        if not canonical_ids:
            return result

        existing_matches = self.db.scalars(
            select(SessionMatch).where(
                SessionMatch.athlete_id == athlete_id
            )
        ).all()

        matched_planned_ids = {
            match.planned_session_id
            for match in existing_matches
        }

        used_canonical_ids = {
            match.canonical_session_id
            for match in existing_matches
        }

        plans = self.db.scalars(
            select(PlannedSession)
            .where(
                PlannedSession.athlete_id == athlete_id,
                PlannedSession.status == "planned",
            )
            .order_by(
                PlannedSession.planned_start_at.asc()
            )
        ).all()

        plans = [
            plan
            for plan in plans
            if plan.id not in matched_planned_ids
        ]

        # Plans carrying an Intervals event ID get first access to
        # canonicals because this is stronger evidence than heuristics.
        plans.sort(
            key=lambda plan: (
                plan.intervals_event_id is None,
                _utc(plan.planned_start_at),
                str(plan.id),
            )
        )

        canonicals = self.db.scalars(
            select(CanonicalSession).where(
                CanonicalSession.athlete_id == athlete_id,
                CanonicalSession.id.in_(canonical_ids),
            )
        ).all()

        canonical_by_id = {
            canonical.id: canonical
            for canonical in canonicals
        }

        event_to_canonicals: dict[
            str,
            set[uuid.UUID],
        ] = {}

        source_rows = self.db.execute(
            select(
                CanonicalSessionSource.canonical_session_id,
                SourceActivity.paired_event_id,
            )
            .join(
                SourceActivity,
                SourceActivity.id
                == CanonicalSessionSource.source_activity_id,
            )
            .where(
                CanonicalSessionSource.canonical_session_id.in_(
                    canonical_ids
                ),
                SourceActivity.paired_event_id.is_not(None),
            )
        ).all()

        for canonical_id, event_id in source_rows:
            if event_id is None:
                continue

            event_to_canonicals.setdefault(
                str(event_id),
                set(),
            ).add(canonical_id)

        for plan in plans:
            available_ids = (
                set(canonical_by_id)
                - used_canonical_ids
            )

            if not available_ids:
                result["no_candidate"] += 1
                continue

            # Strongest evidence: Intervals explicitly says that the
            # activity was paired with the planned calendar event.
            if plan.intervals_event_id is not None:
                direct_ids = (
                    event_to_canonicals.get(
                        str(plan.intervals_event_id),
                        set(),
                    )
                    & available_ids
                )

                if len(direct_ids) == 1:
                    canonical_id = next(iter(direct_ids))

                    self._create_match(
                        plan=plan,
                        canonical=canonical_by_id[
                            canonical_id
                        ],
                        method="intervals_event",
                        score=1.0,
                        evidence={
                            "intervals_event_id":
                                str(plan.intervals_event_id),
                        },
                    )

                    used_canonical_ids.add(canonical_id)

                    result["matched"] += 1
                    result["matched_by_event_id"] += 1
                    continue

                if len(direct_ids) > 1:
                    result["ambiguous"] += 1
                    continue

            scored: list[
                tuple[
                    float,
                    CanonicalSession,
                    dict,
                ]
            ] = []

            for canonical_id in available_ids:
                canonical = canonical_by_id[
                    canonical_id
                ]

                candidate = self._score(
                    plan,
                    canonical,
                )

                if candidate is not None:
                    score, evidence = candidate
                    scored.append(
                        (
                            score,
                            canonical,
                            evidence,
                        )
                    )

            if not scored:
                result["no_candidate"] += 1
                continue

            scored.sort(
                key=lambda item: (
                    -item[0],
                    str(item[1].id),
                )
            )

            best_score, best, evidence = scored[0]

            if best_score < AUTO_MATCH_THRESHOLD:
                result["low_confidence"] += 1
                continue

            if len(scored) > 1:
                second_score = scored[1][0]

                if (
                    best_score - second_score
                    < AUTO_MATCH_MARGIN
                ):
                    result["ambiguous"] += 1
                    continue

            self._create_match(
                plan=plan,
                canonical=best,
                method="auto_score",
                score=best_score,
                evidence=evidence,
            )

            used_canonical_ids.add(best.id)

            result["matched"] += 1
            result["matched_by_score"] += 1

        return result

    @staticmethod
    def _score(
        plan: PlannedSession,
        canonical: CanonicalSession,
    ) -> tuple[float, dict] | None:
        planned_sport = normalize_sport(plan.sport)
        actual_sport = normalize_sport(canonical.sport)

        if (
            not planned_sport
            or planned_sport != actual_sport
        ):
            return None

        delta_s = abs(
            (
                _utc(canonical.start_at)
                - _utc(plan.planned_start_at)
            ).total_seconds()
        )

        if delta_s > MAX_TIME_DELTA_S:
            return None

        time_score = max(
            0.0,
            1.0
            - delta_s / MAX_TIME_DELTA_S,
        )

        duration_score = None

        if (
            plan.planned_duration_s
            and canonical.duration_s
            and plan.planned_duration_s > 0
            and canonical.duration_s > 0
        ):
            duration_score = min(
                plan.planned_duration_s,
                canonical.duration_s,
            ) / max(
                plan.planned_duration_s,
                canonical.duration_s,
            )

            score = (
                0.65 * time_score
                + 0.35 * duration_score
            )
        else:
            score = time_score

        score = round(score, 6)

        return score, {
            "planned_sport": planned_sport,
            "actual_sport": actual_sport,
            "start_delta_s": round(delta_s, 3),
            "time_score": round(time_score, 6),
            "duration_score": (
                round(duration_score, 6)
                if duration_score is not None
                else None
            ),
            "threshold": AUTO_MATCH_THRESHOLD,
        }

    def _create_match(
        self,
        plan: PlannedSession,
        canonical: CanonicalSession,
        method: str,
        score: float,
        evidence: dict,
    ) -> None:
        self.db.add(
            SessionMatch(
                athlete_id=plan.athlete_id,
                planned_session_id=plan.id,
                canonical_session_id=canonical.id,
                match_method=method,
                match_score=score,
                match_evidence=evidence,
                manual_override=False,
            )
        )

        plan.status = "completed"

        self.db.flush()

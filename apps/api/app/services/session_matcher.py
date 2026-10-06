from __future__ import annotations

import uuid
from datetime import datetime, timezone
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.sport import normalize_sport
from app.models.entities import (
    Athlete,
    CanonicalSession,
    CanonicalSessionSource,
    PlannedSession,
    SessionMatch,
    SourceActivity,
    TrainingWeek,
    User,
)


AUTO_MATCH_THRESHOLD = 0.82
AUTO_MATCH_MARGIN = 0.08

# Exact weekday is not a compliance rule.
# Duration / planned volume is the
# dominant heuristic signal.
DURATION_WEIGHT = 0.80
DAY_WEIGHT = 0.15
CLOCK_WEIGHT = 0.05

# Duration within roughly +/-10%
# is treated as essentially equivalent
# for session identity.
DURATION_FULL_SCORE_RATIO = 0.90

# Clock time is only a weak secondary
# signal.
CLOCK_SIGNAL_WINDOW_S = 8 * 60 * 60


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _duration_similarity(
    planned_s: float | None,
    actual_s: float | None,
) -> tuple[
    float | None,
    float | None,
]:
    if (
        planned_s is None
        or actual_s is None
        or planned_s <= 0
        or actual_s <= 0
    ):
        return None, None

    ratio = min(
        planned_s,
        actual_s,
    ) / max(
        planned_s,
        actual_s,
    )

    score = min(
        1.0,
        ratio
        / DURATION_FULL_SCORE_RATIO,
    )

    return (
        round(ratio, 6),
        round(score, 6),
    )


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

        if not plans:
            return result

        athlete = self.db.get(
            Athlete,
            athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
            )

        user = self.db.get(
            User,
            athlete.user_id,
        )

        if user is None:
            raise LookupError(
                "User not found"
            )

        try:
            athlete_zone = ZoneInfo(
                user.timezone
            )

        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                "Invalid athlete timezone"
            ) from exc

        week_ids = {
            plan.training_week_id
            for plan in plans
        }

        weeks = self.db.scalars(
            select(
                TrainingWeek
            ).where(
                TrainingWeek.athlete_id
                == athlete_id,
                TrainingWeek.id.in_(
                    week_ids
                ),
            )
        ).all()

        week_by_id = {
            week.id: week
            for week in weeks
        }

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

            week = week_by_id.get(
                plan.training_week_id
            )

            if week is None:
                result[
                    "no_candidate"
                ] += 1
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
                    plan=plan,
                    canonical=canonical,
                    week=week,
                    athlete_zone=
                        athlete_zone,
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
        *,
        plan: PlannedSession,
        canonical: CanonicalSession,
        week: TrainingWeek,
        athlete_zone: ZoneInfo,
    ) -> tuple[
        float,
        dict,
    ] | None:
        planned_sport = (
            normalize_sport(
                plan.sport
            )
        )

        actual_sport = (
            normalize_sport(
                canonical.sport
            )
        )

        if (
            not planned_sport
            or planned_sport
            != actual_sport
        ):
            return None

        planned_utc = _utc(
            plan.planned_start_at
        )

        actual_utc = _utc(
            canonical.start_at
        )

        planned_local = (
            planned_utc.astimezone(
                athlete_zone
            )
        )

        actual_local = (
            actual_utc.astimezone(
                athlete_zone
            )
        )

        planned_date = (
            planned_local.date()
        )

        actual_date = (
            actual_local.date()
        )

        # Heuristic matching may move
        # a session between weekdays,
        # but never across TrainingWeek
        # boundaries.
        #
        # Explicit Intervals event pairing
        # remains allowed because it is
        # stronger evidence.
        if not (
            week.start_date
            <= actual_date
            <= week.end_date
        ):
            return None

        day_shift = (
            actual_date
            - planned_date
        ).days

        week_span_days = max(
            1,
            (
                week.end_date
                - week.start_date
            ).days
            + 1,
        )

        day_score = max(
            0.0,
            1.0
            - abs(day_shift)
            / week_span_days,
        )

        # Compare time of day separately
        # from weekday. Moving Tuesday
        # 17:00 to Wednesday 17:00 should
        # keep a strong clock signal.
        planned_clock_s = (
            planned_local.hour
            * 3600
            + planned_local.minute
            * 60
            + planned_local.second
        )

        actual_clock_s = (
            actual_local.hour
            * 3600
            + actual_local.minute
            * 60
            + actual_local.second
        )

        clock_delta_s = abs(
            actual_clock_s
            - planned_clock_s
        )

        clock_delta_s = min(
            clock_delta_s,
            86400
            - clock_delta_s,
        )

        clock_score = max(
            0.0,
            1.0
            - clock_delta_s
            / CLOCK_SIGNAL_WINDOW_S,
        )

        (
            duration_ratio,
            duration_score,
        ) = _duration_similarity(
            plan.planned_duration_s,
            canonical.duration_s,
        )

        if duration_score is not None:
            score = (
                DURATION_WEIGHT
                * duration_score
                + DAY_WEIGHT
                * day_score
                + CLOCK_WEIGHT
                * clock_score
            )

        else:
            # Without duration we remain
            # conservative because weekday
            # alone is weak evidence.
            score = (
                0.75 * day_score
                + 0.25 * clock_score
            )

        absolute_start_delta_s = abs(
            (
                actual_utc
                - planned_utc
            ).total_seconds()
        )

        score = round(
            score,
            6,
        )

        return score, {
            "planned_sport":
                planned_sport,
            "actual_sport":
                actual_sport,
            "training_week_id":
                str(week.id),
            "schedule_policy":
                "flexible_within_week",
            "planned_local_date":
                planned_date.isoformat(),
            "actual_local_date":
                actual_date.isoformat(),
            "day_shift":
                day_shift,
            "schedule_shifted":
                day_shift != 0,
            "absolute_start_delta_s":
                round(
                    absolute_start_delta_s,
                    3,
                ),
            "clock_delta_s":
                round(
                    clock_delta_s,
                    3,
                ),
            "day_score":
                round(
                    day_score,
                    6,
                ),
            "clock_score":
                round(
                    clock_score,
                    6,
                ),
            "duration_ratio":
                duration_ratio,
            "duration_score":
                duration_score,
            "weights": {
                "duration":
                    DURATION_WEIGHT,
                "day":
                    DAY_WEIGHT,
                "clock":
                    CLOCK_WEIGHT,
            },
            "threshold":
                AUTO_MATCH_THRESHOLD,
            "ambiguity_margin":
                AUTO_MATCH_MARGIN,
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

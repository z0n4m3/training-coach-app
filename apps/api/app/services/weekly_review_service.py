from __future__ import annotations

import uuid
from collections import Counter
from datetime import (
    datetime,
    time,
    timedelta,
    timezone,
)
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
    PlannedSession,
    SessionAnalysis,
    SessionFeedback,
    SessionMatch,
    TrainingWeek,
    User,
    WeeklyReview,
    utcnow,
)


WEEKLY_REVIEW_VERSION = (
    "deterministic-weekly-v1"
)


def _utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _sum_metric(
    items,
    attribute: str,
) -> float:
    return round(
        sum(
            float(value)
            for item in items
            if (
                value := getattr(
                    item,
                    attribute,
                    None,
                )
            )
            is not None
        ),
        3,
    )


def _known_count(
    items,
    attribute: str,
) -> int:
    return sum(
        1
        for item in items
        if getattr(
            item,
            attribute,
            None,
        )
        is not None
    )


def _ratio(
    numerator: float,
    denominator: float,
) -> float | None:
    if denominator <= 0:
        return None

    return round(
        numerator / denominator,
        4,
    )


def _average(
    values: list[float],
) -> float | None:
    if not values:
        return None

    return round(
        sum(values) / len(values),
        2,
    )


def _counter_dict(
    counter: Counter,
) -> dict:
    return {
        key: counter[key]
        for key in sorted(counter)
    }


class WeeklyReviewService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        *,
        athlete_id: uuid.UUID,
        week_id: uuid.UUID,
    ) -> dict | None:
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
            return None

        return self._serialize(
            review
        )

    def rebuild(
        self,
        *,
        athlete_id: uuid.UUID,
        week_id: uuid.UUID,
    ) -> dict:
        (
            week,
            athlete,
            user,
        ) = self._owned_week(
            athlete_id=athlete_id,
            week_id=week_id,
        )

        (
            window_start,
            window_end,
            athlete_zone,
        ) = self._week_window(
            week=week,
            user=user,
        )

        now_local_date = (
            utcnow()
            .astimezone(
                athlete_zone
            )
            .date()
        )

        if now_local_date < week.start_date:
            period_status = "future"

        elif now_local_date > week.end_date:
            period_status = "complete"

        else:
            period_status = "in_progress"

        planned = list(
            self.db.scalars(
                select(
                    PlannedSession
                )
                .where(
                    PlannedSession
                    .training_week_id
                    == week.id,
                    PlannedSession
                    .athlete_id
                    == athlete_id,
                )
                .order_by(
                    PlannedSession
                    .planned_start_at
                    .asc()
                )
            )
        )

        planned_ids = {
            item.id
            for item in planned
        }

        week_matches = []

        if planned_ids:
            week_matches = list(
                self.db.scalars(
                    select(
                        SessionMatch
                    ).where(
                        SessionMatch
                        .athlete_id
                        == athlete_id,
                        SessionMatch
                        .planned_session_id
                        .in_(
                            planned_ids
                        ),
                    )
                )
            )

        match_by_plan = {
            match.planned_session_id:
                match
            for match in week_matches
        }

        matched_actual_ids = {
            match.canonical_session_id
            for match in week_matches
        }

        matched_actual_by_id = {}

        if matched_actual_ids:
            matched_actuals = list(
                self.db.scalars(
                    select(
                        CanonicalSession
                    ).where(
                        CanonicalSession
                        .athlete_id
                        == athlete_id,
                        CanonicalSession.id.in_(
                            matched_actual_ids
                        ),
                    )
                )
            )

            matched_actual_by_id = {
                item.id: item
                for item in matched_actuals
            }

        actuals = list(
            self.db.scalars(
                select(
                    CanonicalSession
                )
                .where(
                    CanonicalSession
                    .athlete_id
                    == athlete_id,
                    CanonicalSession.start_at
                    >= window_start,
                    CanonicalSession.start_at
                    < window_end,
                )
                .order_by(
                    CanonicalSession
                    .start_at
                    .asc()
                )
            )
        )

        actual_ids = {
            item.id
            for item in actuals
        }

        actual_matches = []

        if actual_ids:
            actual_matches = list(
                self.db.scalars(
                    select(
                        SessionMatch
                    ).where(
                        SessionMatch
                        .athlete_id
                        == athlete_id,
                        SessionMatch
                        .canonical_session_id
                        .in_(
                            actual_ids
                        ),
                    )
                )
            )

        plan_ids_by_actual: dict[
            uuid.UUID,
            list[uuid.UUID],
        ] = {}

        for match in actual_matches:
            plan_ids_by_actual.setdefault(
                match.canonical_session_id,
                [],
            ).append(
                match.planned_session_id
            )

        analyses = []

        if actual_ids:
            analyses = list(
                self.db.scalars(
                    select(
                        SessionAnalysis
                    ).where(
                        SessionAnalysis
                        .athlete_id
                        == athlete_id,
                        SessionAnalysis
                        .canonical_session_id
                        .in_(
                            actual_ids
                        ),
                    )
                )
            )

        analysis_by_actual = {
            item.canonical_session_id:
                item
            for item in analyses
        }

        feedback_rows = []

        if actual_ids:
            feedback_rows = list(
                self.db.scalars(
                    select(
                        SessionFeedback
                    ).where(
                        SessionFeedback
                        .athlete_id
                        == athlete_id,
                        SessionFeedback
                        .canonical_session_id
                        .in_(
                            actual_ids
                        ),
                    )
                )
            )

        feedback_by_actual = {
            item.canonical_session_id:
                item
            for item in feedback_rows
        }

        matched_planned = [
            item
            for item in planned
            if item.id in match_by_plan
        ]

        matched_planned_count = len(
            matched_planned
        )

        unmatched_planned_count = (
            len(planned)
            - matched_planned_count
        )

        session_completion_ratio = (
            None
            if not planned
            else round(
                matched_planned_count
                / len(planned),
                4,
            )
        )

        planned_duration_s = (
            _sum_metric(
                planned,
                "planned_duration_s",
            )
        )

        completed_planned_duration_s = (
            _sum_metric(
                matched_planned,
                "planned_duration_s",
            )
        )

        planned_volume_completion_ratio = (
            _ratio(
                completed_planned_duration_s,
                planned_duration_s,
            )
        )

        matched_actuals_for_plan = [
            matched_actual_by_id[
                match.canonical_session_id
            ]
            for match in week_matches
            if match.canonical_session_id
            in matched_actual_by_id
        ]

        matched_actual_duration_s = (
            _sum_metric(
                matched_actuals_for_plan,
                "duration_s",
            )
        )

        actual_vs_total_planned_duration_ratio = (
            _ratio(
                matched_actual_duration_s,
                planned_duration_s,
            )
        )

        priority_summary = {}

        for priority in (
            "KEY",
            "SUPPORT",
            "EASY",
        ):
            priority_planned = [
                item
                for item in planned
                if item.priority
                == priority
            ]

            priority_matched = [
                item
                for item
                in priority_planned
                if item.id
                in match_by_plan
            ]

            priority_planned_duration = (
                _sum_metric(
                    priority_planned,
                    "planned_duration_s",
                )
            )

            priority_completed_duration = (
                _sum_metric(
                    priority_matched,
                    "planned_duration_s",
                )
            )

            priority_summary[
                priority
            ] = {
                "planned":
                    len(
                        priority_planned
                    ),
                "matched":
                    len(
                        priority_matched
                    ),
                "unmatched":
                    (
                        len(
                            priority_planned
                        )
                        - len(
                            priority_matched
                        )
                    ),
                "planned_duration_s":
                    priority_planned_duration,
                "completed_planned_duration_s":
                    priority_completed_duration,
                "planned_volume_completion_ratio":
                    _ratio(
                        priority_completed_duration,
                        priority_planned_duration,
                    ),
            }

        shifted_session_count = 0
        same_day_session_count = 0
        schedule_shift_days: list[
            int
        ] = []

        matched_outside_window_count = 0

        planned_by_id = {
            item.id: item
            for item in planned
        }

        for match in week_matches:
            plan = planned_by_id.get(
                match.planned_session_id
            )

            actual = matched_actual_by_id.get(
                match.canonical_session_id
            )

            if (
                plan is None
                or actual is None
            ):
                continue

            planned_local_date = (
                _utc(
                    plan.planned_start_at
                )
                .astimezone(
                    athlete_zone
                )
                .date()
            )

            actual_local_date = (
                _utc(
                    actual.start_at
                )
                .astimezone(
                    athlete_zone
                )
                .date()
            )

            shift_days = (
                actual_local_date
                - planned_local_date
            ).days

            schedule_shift_days.append(
                shift_days
            )

            if shift_days == 0:
                same_day_session_count += 1
            else:
                shifted_session_count += 1

            actual_utc = _utc(
                actual.start_at
            )

            if not (
                window_start
                <= actual_utc
                < window_end
            ):
                matched_outside_window_count += 1

        unplanned_actuals = [
            item
            for item in actuals
            if item.id
            not in plan_ids_by_actual
        ]

        classification_counts = Counter(
            item.classification
            for item in analyses
        )

        analysis_version_counts = Counter(
            item.analysis_version
            for item in analyses
        )

        session_flag_counts = Counter()
        duration_status_counts = Counter()
        stimulus_status_counts = Counter()
        subjective_status_counts = Counter()

        for analysis in analyses:
            for flag in (
                analysis.flags
                or []
            ):
                if isinstance(
                    flag,
                    str,
                ):
                    session_flag_counts[
                        flag
                    ] += 1

            evidence = (
                analysis.evidence
                or {}
            )

            duration = evidence.get(
                "duration_assessment"
            )

            if isinstance(
                duration,
                dict,
            ):
                status = duration.get(
                    "status"
                )

                if status:
                    duration_status_counts[
                        str(status)
                    ] += 1

            stimulus = evidence.get(
                "stimulus_assessment"
            )

            if isinstance(
                stimulus,
                dict,
            ):
                status = stimulus.get(
                    "status"
                )

                if status:
                    stimulus_status_counts[
                        str(status)
                    ] += 1

            subjective = evidence.get(
                "subjective_response"
            )

            if isinstance(
                subjective,
                dict,
            ):
                status = subjective.get(
                    "status"
                )

                if status:
                    subjective_status_counts[
                        str(status)
                    ] += 1

        rpe_values = [
            float(item.rpe)
            for item in feedback_rows
            if item.rpe is not None
        ]

        leg_values = [
            float(
                item.leg_fatigue
            )
            for item in feedback_rows
            if item.leg_fatigue
            is not None
        ]

        comment_count = sum(
            1
            for item in feedback_rows
            if (
                item.comment
                and item.comment.strip()
            )
        )

        custom_metrics_count = sum(
            1
            for item in feedback_rows
            if item.custom_metrics
        )

        feedback_coverage = (
            None
            if not actuals
            else round(
                len(feedback_rows)
                / len(actuals),
                4,
            )
        )

        by_sport: dict[
            str,
            dict,
        ] = {}

        for actual in actuals:
            sport = (
                normalize_sport(
                    actual.sport
                )
                or "unknown"
            )

            item = by_sport.setdefault(
                sport,
                {
                    "session_count": 0,
                    "duration_s": 0.0,
                    "training_load": 0.0,
                    "training_load_known_count": 0,
                    "work_kj": 0.0,
                    "work_kj_known_count": 0,
                    "distance_m_descriptive": 0.0,
                    "distance_known_count": 0,
                },
            )

            item[
                "session_count"
            ] += 1

            if (
                actual.duration_s
                is not None
            ):
                item[
                    "duration_s"
                ] += float(
                    actual.duration_s
                )

            if (
                actual.training_load
                is not None
            ):
                item[
                    "training_load"
                ] += float(
                    actual.training_load
                )
                item[
                    "training_load_known_count"
                ] += 1

            if (
                actual.work_kj
                is not None
            ):
                item[
                    "work_kj"
                ] += float(
                    actual.work_kj
                )
                item[
                    "work_kj_known_count"
                ] += 1

            if (
                actual.distance_m
                is not None
            ):
                item[
                    "distance_m_descriptive"
                ] += float(
                    actual.distance_m
                )
                item[
                    "distance_known_count"
                ] += 1

        for item in by_sport.values():
            for key in (
                "duration_s",
                "training_load",
                "work_kj",
                "distance_m_descriptive",
            ):
                item[key] = round(
                    item[key],
                    3,
                )

        flags: list[str] = []

        # A shifted weekday is deliberately
        # NOT a compliance problem.

        if (
            period_status == "complete"
            and unmatched_planned_count
        ):
            flags.append(
                "unmatched_planned_sessions_present"
            )

        if unplanned_actuals:
            flags.append(
                "unplanned_actual_sessions_present"
            )

        if len(analyses) < len(actuals):
            flags.append(
                "analysis_missing"
            )

        if len(feedback_rows) < len(actuals):
            flags.append(
                "feedback_missing"
            )

        if matched_outside_window_count:
            flags.append(
                "matched_outside_load_window_present"
            )

        summary = {
            "week": {
                "training_week_id":
                    str(week.id),
                "week_number":
                    week.week_number,
                "start_date":
                    week.start_date
                    .isoformat(),
                "end_date":
                    week.end_date
                    .isoformat(),
                "timezone":
                    user.timezone,
                "period_status":
                    period_status,
                "window_start_utc":
                    window_start
                    .isoformat(),
                "window_end_utc":
                    window_end
                    .isoformat(),
            },

            "plan_execution": {
                "planned_session_count":
                    len(planned),
                "matched_planned_count":
                    matched_planned_count,
                "unmatched_planned_count":
                    unmatched_planned_count,
                "session_completion_ratio":
                    session_completion_ratio,

                # Planned duration is the
                # primary volume dimension.
                "planned_duration_s":
                    planned_duration_s,
                "planned_duration_known_count":
                    _known_count(
                        planned,
                        "planned_duration_s",
                    ),
                "completed_planned_duration_s":
                    completed_planned_duration_s,
                "planned_volume_completion_ratio":
                    planned_volume_completion_ratio,

                # Actual duration of sessions
                # linked to this plan.
                "matched_actual_duration_s":
                    matched_actual_duration_s,
                "actual_vs_total_planned_duration_ratio":
                    actual_vs_total_planned_duration_ratio,

                "by_priority":
                    priority_summary,
            },

            "schedule": {
                # Informational only.
                # Moving Tuesday -> Wednesday
                # is not a compliance penalty.
                "same_day_session_count":
                    same_day_session_count,
                "shifted_session_count":
                    shifted_session_count,
                "shift_days":
                    schedule_shift_days,
                "max_abs_shift_days":
                    (
                        None
                        if not schedule_shift_days
                        else max(
                            abs(value)
                            for value
                            in schedule_shift_days
                        )
                    ),
                "matched_outside_load_window_count":
                    matched_outside_window_count,
            },

            # Physical work belongs to the
            # week in which it actually
            # happened.
            "actual_load_window": {
                "session_count":
                    len(actuals),
                "unplanned_session_count":
                    len(
                        unplanned_actuals
                    ),
                "duration_s":
                    _sum_metric(
                        actuals,
                        "duration_s",
                    ),
                "duration_known_count":
                    _known_count(
                        actuals,
                        "duration_s",
                    ),
                "training_load":
                    _sum_metric(
                        actuals,
                        "training_load",
                    ),
                "training_load_known_count":
                    _known_count(
                        actuals,
                        "training_load",
                    ),
                "work_kj":
                    _sum_metric(
                        actuals,
                        "work_kj",
                    ),
                "work_kj_known_count":
                    _known_count(
                        actuals,
                        "work_kj",
                    ),

                # Distance is descriptive
                # telemetry only.
                "cycling_distance_m_descriptive":
                    round(
                        sum(
                            float(
                                item.distance_m
                            )
                            for item
                            in actuals
                            if (
                                item.distance_m
                                is not None
                                and normalize_sport(
                                    item.sport
                                )
                                == "cycling"
                            )
                        ),
                        3,
                    ),

                "by_sport":
                    by_sport,
            },

            "analysis": {
                "analyzed_session_count":
                    len(analyses),
                "missing_analysis_count":
                    (
                        len(actuals)
                        - len(analyses)
                    ),
                "classification_counts":
                    _counter_dict(
                        classification_counts
                    ),
                "analysis_version_counts":
                    _counter_dict(
                        analysis_version_counts
                    ),
                "duration_status_counts":
                    _counter_dict(
                        duration_status_counts
                    ),
                "stimulus_status_counts":
                    _counter_dict(
                        stimulus_status_counts
                    ),
                "subjective_status_counts":
                    _counter_dict(
                        subjective_status_counts
                    ),
                "session_flag_counts":
                    _counter_dict(
                        session_flag_counts
                    ),
            },

            "feedback": {
                "feedback_count":
                    len(
                        feedback_rows
                    ),
                "coverage":
                    feedback_coverage,
                "rpe_count":
                    len(rpe_values),
                "rpe_avg_descriptive":
                    _average(
                        rpe_values
                    ),
                "leg_fatigue_count":
                    len(leg_values),
                "leg_fatigue_avg_descriptive":
                    _average(
                        leg_values
                    ),
                "comment_count":
                    comment_count,

                # Individual custom metrics
                # remain opaque to generic
                # weekly rules.
                "custom_metrics_session_count":
                    custom_metrics_count,
            },

            "planned_sessions": [
                {
                    "planned_session_id":
                        str(item.id),
                    "name":
                        item.name,
                    "sport":
                        normalize_sport(
                            item.sport
                        ),
                    "session_type":
                        item.session_type,
                    "priority":
                        item.priority,
                    "planned_duration_s":
                        item
                        .planned_duration_s,
                    "matched":
                        item.id
                        in match_by_plan,
                    "canonical_session_id":
                        (
                            None
                            if item.id
                            not in match_by_plan
                            else str(
                                match_by_plan[
                                    item.id
                                ]
                                .canonical_session_id
                            )
                        ),
                }
                for item in planned
            ],

            "actual_sessions": [
                {
                    "canonical_session_id":
                        str(item.id),
                    "sport":
                        normalize_sport(
                            item.sport
                        ),
                    "start_at":
                        _utc(
                            item.start_at
                        ).isoformat(),
                    "duration_s":
                        item.duration_s,
                    "training_load":
                        item.training_load,
                    "work_kj":
                        item.work_kj,
                    "distance_m_descriptive":
                        item.distance_m,
                    "planned_session_ids":
                        [
                            str(plan_id)
                            for plan_id in (
                                plan_ids_by_actual
                                .get(
                                    item.id,
                                    [],
                                )
                            )
                        ],
                    "analysis_status":
                        (
                            "missing"
                            if item.id
                            not in analysis_by_actual
                            else (
                                analysis_by_actual[
                                    item.id
                                ]
                                .classification
                            )
                        ),
                    "feedback_available":
                        item.id
                        in feedback_by_actual,
                }
                for item in actuals
            ],
        }

        review = self.db.scalar(
            select(
                WeeklyReview
            ).where(
                WeeklyReview
                .athlete_id
                == athlete_id,
                WeeklyReview
                .training_week_id
                == week.id,
            )
        )

        if review is None:
            review = WeeklyReview(
                athlete_id=athlete_id,
                training_week_id=
                    week.id,
                review_version=
                    WEEKLY_REVIEW_VERSION,
                summary=summary,
                flags=flags,
                generated_at=utcnow(),
            )

            self.db.add(
                review
            )

        else:
            review.review_version = (
                WEEKLY_REVIEW_VERSION
            )
            review.summary = summary
            review.flags = flags
            review.generated_at = utcnow()

        self.db.commit()
        self.db.refresh(
            review
        )

        return self._serialize(
            review
        )

    def _owned_week(
        self,
        *,
        athlete_id: uuid.UUID,
        week_id: uuid.UUID,
    ) -> tuple[
        TrainingWeek,
        Athlete,
        User,
    ]:
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

        return (
            week,
            athlete,
            user,
        )

    @staticmethod
    def _week_window(
        *,
        week: TrainingWeek,
        user: User,
    ) -> tuple[
        datetime,
        datetime,
        ZoneInfo,
    ]:
        try:
            zone = ZoneInfo(
                user.timezone
            )

        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                "Invalid athlete timezone"
            ) from exc

        start_local = datetime.combine(
            week.start_date,
            time.min,
            tzinfo=zone,
        )

        end_local = datetime.combine(
            (
                week.end_date
                + timedelta(days=1)
            ),
            time.min,
            tzinfo=zone,
        )

        return (
            start_local.astimezone(
                timezone.utc
            ),
            end_local.astimezone(
                timezone.utc
            ),
            zone,
        )

    @staticmethod
    def _serialize(
        review: WeeklyReview,
    ) -> dict:
        return {
            "id":
                review.id,
            "athlete_id":
                review.athlete_id,
            "training_week_id":
                review.training_week_id,
            "review_version":
                review.review_version,
            "summary":
                review.summary,
            "flags":
                review.flags or [],
            "generated_at":
                review.generated_at,
            "created_at":
                review.created_at,
            "updated_at":
                review.updated_at,
        }

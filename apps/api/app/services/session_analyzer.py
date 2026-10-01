from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    CanonicalSession,
    PlannedSession,
    SessionAnalysis,
    SessionMatch,
)
from app.services.performance_profile_service import (
    PerformanceProfileService,
)


ANALYSIS_VERSION = "deterministic-v3"

WITHIN_TOLERANCE = 0.10
MAJOR_DEVIATION = 0.25


def _comparison(
    actual: float | None,
    planned: float | None,
) -> dict | None:
    if (
        actual is None
        or planned is None
        or planned <= 0
    ):
        return None

    delta = actual - planned
    deviation = delta / planned
    absolute_deviation = abs(deviation)

    if absolute_deviation <= WITHIN_TOLERANCE:
        level = "within"
    elif absolute_deviation <= MAJOR_DEVIATION:
        level = "minor"
    else:
        level = "major"

    if delta > 0:
        direction = "over"
    elif delta < 0:
        direction = "under"
    else:
        direction = "exact"

    return {
        "planned": round(float(planned), 3),
        "actual": round(float(actual), 3),
        "delta": round(float(delta), 3),
        "ratio": round(float(actual / planned), 6),
        "deviation_pct": round(
            float(deviation * 100),
            3,
        ),
        "level": level,
        "direction": direction,
    }


def _ratio(
    value: float | None,
    denominator: float | None,
) -> float | None:
    if (
        value is None
        or denominator is None
        or denominator <= 0
    ):
        return None

    return round(
        float(value / denominator),
        6,
    )


def _percent(
    value: float | None,
    denominator: float | None,
) -> float | None:
    ratio = _ratio(
        value,
        denominator,
    )

    if ratio is None:
        return None

    return round(
        ratio * 100,
        2,
    )


def _duration_assessment(
    actual: float | None,
    planned: float | None,
) -> dict:
    comparison = _comparison(
        actual,
        planned,
    )

    if comparison is None:
        return {
            "status": "not_comparable",
            "comparison": None,
        }

    return {
        "status": comparison["level"],
        "comparison": comparison,
    }


def _is_interval_structure(
    structure: dict[str, Any] | None,
) -> bool:
    if not structure:
        return False

    structure_type = str(
        structure.get("type") or ""
    ).lower()

    if structure_type in {
        "interval",
        "intervals",
        "repeats",
        "structured_intervals",
    }:
        return True

    return any(
        key in structure
        for key in {
            "intervals",
            "steps",
            "repeats",
            "work_intervals",
        }
    )


def _target(
    targets: dict[str, Any] | None,
    name: str,
    allowed_metrics: set[str],
) -> tuple[dict | None, str | None]:
    if not targets:
        return None, None

    raw = targets.get(name)

    if raw is None:
        return None, None

    if not isinstance(raw, dict):
        return None, "invalid"

    metric = raw.get("metric")

    if metric not in allowed_metrics:
        return None, "unsupported_metric"

    try:
        minimum = float(raw["min"])
        maximum = float(raw["max"])
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return None, "invalid"

    if (
        minimum < 0
        or maximum <= 0
        or minimum > maximum
    ):
        return None, "invalid"

    return {
        "metric": metric,
        "min": round(minimum, 2),
        "max": round(maximum, 2),
    }, None


def _single_target_assessment(
    performance: dict,
    target: dict,
) -> dict:
    actual = performance.get(
        target["metric"]
    )

    if actual is None:
        return {
            "status": "performance_missing",
            "metric": target["metric"],
            "actual": None,
            "target": target,
        }

    if actual < target["min"]:
        status = "below_target"
    elif actual > target["max"]:
        status = "above_target"
    else:
        status = "aligned"

    return {
        "status": status,
        "metric": target["metric"],
        "actual": actual,
        "target": target,
    }


def _stimulus_assessment(
    *,
    plan: PlannedSession,
    performance: dict,
) -> tuple[dict, list[str]]:
    flags: list[str] = []

    if _is_interval_structure(
        plan.workout_structure
    ):
        flags.append(
            "stimulus_requires_interval_analysis"
        )

        return {
            "status":
                "interval_analysis_required",
            "power": None,
            "hr": None,
        }, flags

    power_target, power_error = _target(
        plan.targets,
        "power",
        {
            "avg_power_pct_ftp",
            "normalized_power_pct_ftp",
        },
    )

    hr_target, hr_error = _target(
        plan.targets,
        "hr",
        {
            "avg_hr_pct_threshold",
        },
    )

    if (
        power_error is not None
        or hr_error is not None
    ):
        flags.append(
            "stimulus_target_invalid"
        )

        return {
            "status": "target_invalid",
            "power": None,
            "hr": None,
        }, flags

    if (
        power_target is None
        and hr_target is None
    ):
        return {
            "status": "target_missing",
            "power": None,
            "hr": None,
        }, flags

    power = (
        _single_target_assessment(
            performance,
            power_target,
        )
        if power_target is not None
        else None
    )

    hr = (
        _single_target_assessment(
            performance,
            hr_target,
        )
        if hr_target is not None
        else None
    )

    assessments = [
        ("power", power),
        ("hr", hr),
    ]

    statuses: set[str] = set()

    for name, item in assessments:
        if item is None:
            continue

        status = item["status"]
        statuses.add(status)

        if status != "aligned":
            flags.append(
                f"{name}_{status}"
            )

    measurable = {
        status
        for status in statuses
        if status != "performance_missing"
    }

    if not measurable:
        overall = "performance_missing"
    elif (
        "above_target" in measurable
        and "below_target" in measurable
    ):
        overall = "mixed"
    elif "above_target" in measurable:
        overall = "above_target"
    elif "below_target" in measurable:
        overall = "below_target"
    else:
        overall = "aligned"

    if overall in {
        "above_target",
        "below_target",
        "mixed",
    }:
        flags.append(
            f"stimulus_{overall}"
        )

    return {
        "status": overall,
        "power": power,
        "hr": hr,
    }, flags


class SessionAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def analyze(
        self,
        athlete_id: uuid.UUID,
        canonical_ids: set[uuid.UUID],
    ) -> dict:
        result = {
            "analyzed": 0,
            "matched": 0,
            "unplanned": 0,
            "match_conflict": 0,
            "duration_within": 0,
            "duration_minor": 0,
            "duration_major": 0,
            "duration_not_comparable": 0,
            "stimulus_aligned": 0,
            "stimulus_above_target": 0,
            "stimulus_below_target": 0,
            "stimulus_mixed": 0,
            "stimulus_target_missing": 0,
            "stimulus_target_invalid": 0,
            "stimulus_performance_missing": 0,
            "stimulus_interval_analysis_required": 0,
        }

        if not canonical_ids:
            return result

        canonicals = self.db.scalars(
            select(CanonicalSession)
            .where(
                CanonicalSession.athlete_id
                == athlete_id,
                CanonicalSession.id.in_(
                    canonical_ids
                ),
            )
            .order_by(
                CanonicalSession.start_at.asc()
            )
        ).all()

        for canonical in canonicals:
            payload = self._analyze_one(
                athlete_id=athlete_id,
                canonical=canonical,
            )

            analysis = self.db.scalar(
                select(SessionAnalysis).where(
                    SessionAnalysis.canonical_session_id
                    == canonical.id
                )
            )

            if analysis is None:
                analysis = SessionAnalysis(
                    athlete_id=athlete_id,
                    canonical_session_id=
                        canonical.id,
                    classification=payload[
                        "classification"
                    ],
                )
                self.db.add(analysis)

            analysis.athlete_id = athlete_id
            analysis.planned_session_id = (
                payload["planned_session_id"]
            )
            analysis.analysis_version = (
                ANALYSIS_VERSION
            )
            analysis.classification = (
                payload["classification"]
            )
            analysis.evidence = payload[
                "evidence"
            ]
            analysis.flags = payload[
                "flags"
            ]

            canonical.analysis_level = (
                "deterministic"
            )

            result["analyzed"] += 1
            result[
                payload["classification"]
            ] += 1

            if (
                payload["classification"]
                == "matched"
            ):
                duration_status = payload[
                    "evidence"
                ]["duration_assessment"][
                    "status"
                ]

                stimulus_status = payload[
                    "evidence"
                ]["stimulus_assessment"][
                    "status"
                ]

                result[
                    f"duration_{duration_status}"
                ] += 1

                result[
                    f"stimulus_{stimulus_status}"
                ] += 1

        self.db.flush()

        return result

    def _performance_evidence(
        self,
        athlete_id: uuid.UUID,
        canonical: CanonicalSession,
    ) -> tuple[dict, list[str]]:
        flags: list[str] = []

        if canonical.indoor is True:
            context = "indoor"
        elif canonical.indoor is False:
            context = "outdoor"
        else:
            context = None

        if context is None:
            flags.append(
                "performance_context_unknown"
            )

            return {
                "status":
                    "context_unknown",
                "context": None,
                "zone_set_id": None,
                "ftp_w": None,
                "threshold_hr_bpm": None,
                "avg_power_pct_ftp": None,
                "normalized_power_pct_ftp":
                    None,
                "intensity_factor": None,
                "avg_hr_pct_threshold": None,
                "max_hr_pct_threshold": None,
            }, flags

        zone_set = (
            PerformanceProfileService(
                self.db
            ).effective_zone_set(
                athlete_id=athlete_id,
                sport=canonical.sport,
                context=context,
                at=canonical.start_at,
            )
        )

        if zone_set is None:
            flags.append(
                "no_effective_zone_set"
            )

            return {
                "status":
                    "zone_set_missing",
                "context": context,
                "zone_set_id": None,
                "ftp_w": None,
                "threshold_hr_bpm": None,
                "avg_power_pct_ftp": None,
                "normalized_power_pct_ftp":
                    None,
                "intensity_factor": None,
                "avg_hr_pct_threshold": None,
                "max_hr_pct_threshold": None,
            }, flags

        ftp_w = zone_set["ftp_w"]
        threshold_hr = zone_set[
            "threshold_hr_bpm"
        ]

        return {
            "status": "available",
            "context": context,
            "zone_set_id": str(
                zone_set["id"]
            ),
            "effective_from":
                zone_set[
                    "effective_from"
                ].isoformat(),
            "ftp_w": ftp_w,
            "threshold_hr_bpm":
                threshold_hr,
            "avg_power_pct_ftp":
                _percent(
                    canonical.avg_power_w,
                    ftp_w,
                ),
            "normalized_power_pct_ftp":
                _percent(
                    canonical.normalized_power_w,
                    ftp_w,
                ),
            "intensity_factor":
                _ratio(
                    canonical.normalized_power_w,
                    ftp_w,
                ),
            "avg_hr_pct_threshold":
                _percent(
                    canonical.avg_hr_bpm,
                    threshold_hr,
                ),
            "max_hr_pct_threshold":
                _percent(
                    canonical.max_hr_bpm,
                    threshold_hr,
                ),
        }, flags

    def _analyze_one(
        self,
        athlete_id: uuid.UUID,
        canonical: CanonicalSession,
    ) -> dict:
        performance, performance_flags = (
            self._performance_evidence(
                athlete_id,
                canonical,
            )
        )

        matches = self.db.scalars(
            select(SessionMatch).where(
                SessionMatch.athlete_id
                == athlete_id,
                SessionMatch.canonical_session_id
                == canonical.id,
            )
        ).all()

        actual = {
            "duration_s":
                canonical.duration_s,
            "distance_m":
                canonical.distance_m,
            "training_load":
                canonical.training_load,
            "avg_power_w":
                canonical.avg_power_w,
            "normalized_power_w":
                canonical.normalized_power_w,
            "avg_hr_bpm":
                canonical.avg_hr_bpm,
            "max_hr_bpm":
                canonical.max_hr_bpm,
        }

        if not matches:
            return {
                "planned_session_id": None,
                "classification":
                    "unplanned",
                "flags": [
                    "no_planned_session_match",
                    *performance_flags,
                ],
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                    "match_count": 0,
                },
            }

        if len(matches) > 1:
            return {
                "planned_session_id": None,
                "classification":
                    "match_conflict",
                "flags": [
                    "multiple_plan_matches",
                    *performance_flags,
                ],
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                    "match_count":
                        len(matches),
                },
            }

        match = matches[0]

        plan = self.db.get(
            PlannedSession,
            match.planned_session_id,
        )

        if (
            plan is None
            or plan.athlete_id != athlete_id
        ):
            return {
                "planned_session_id": None,
                "classification":
                    "match_conflict",
                "flags": [
                    "invalid_plan_match",
                    *performance_flags,
                ],
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                },
            }

        duration = _duration_assessment(
            canonical.duration_s,
            plan.planned_duration_s,
        )

        stimulus, stimulus_flags = (
            _stimulus_assessment(
                plan=plan,
                performance=performance,
            )
        )

        flags = [
            *performance_flags,
            *stimulus_flags,
        ]

        duration_comparison = (
            duration["comparison"]
        )

        if (
            duration_comparison is not None
            and duration_comparison["level"]
            != "within"
        ):
            flags.append(
                (
                    "duration_"
                    f"{duration_comparison['direction']}_"
                    f"{duration_comparison['level']}"
                )
            )

        return {
            "planned_session_id":
                plan.id,
            "classification":
                "matched",
            "flags":
                flags,
            "evidence": {
                "actual":
                    actual,
                "performance":
                    performance,
                "duration_assessment":
                    duration,
                "stimulus_assessment":
                    stimulus,
                "planned": {
                    "duration_s":
                        plan.planned_duration_s,
                    "session_type":
                        plan.session_type,
                    "priority":
                        plan.priority,
                    "targets":
                        plan.targets,
                    "workout_structure":
                        plan.workout_structure,
                },
                "match": {
                    "method":
                        match.match_method,
                    "score":
                        match.match_score,
                    "manual_override":
                        match.manual_override,
                },
            },
        }

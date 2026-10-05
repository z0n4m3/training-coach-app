from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    CanonicalSession,
    PlannedSession,
    SessionAnalysis,
    SessionFeedback,
    SessionMatch,
)
from app.services.performance_profile_service import (
    PerformanceProfileService,
)
from app.services.training_setup_service import (
    TrainingSetupService,
)


ANALYSIS_VERSION = "deterministic-v6"

WITHIN_TOLERANCE = 0.10
MAJOR_DEVIATION = 0.25

# Product heuristic, not a diagnosis.
# >= 4/5 means the signal should be visible
# to later coaching logic.
HIGH_LEG_FATIGUE = 4.0


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



def _rpe_target(
    targets: dict[str, Any] | None,
) -> tuple[dict | None, str | None]:
    if not targets:
        return None, None

    raw = targets.get("rpe")

    if raw is None:
        return None, None

    if (
        isinstance(raw, (list, tuple))
        and len(raw) == 2
    ):
        minimum_raw = raw[0]
        maximum_raw = raw[1]

    elif isinstance(raw, dict):
        try:
            minimum_raw = raw["min"]
            maximum_raw = raw["max"]
        except KeyError:
            return None, "invalid"

    else:
        return None, "invalid"

    try:
        minimum = float(minimum_raw)
        maximum = float(maximum_raw)

    except (
        TypeError,
        ValueError,
    ):
        return None, "invalid"

    if (
        minimum < 0
        or maximum > 10
        or minimum > maximum
    ):
        return None, "invalid"

    return {
        "min": round(minimum, 2),
        "max": round(maximum, 2),
    }, None


def _subjective_response(
    *,
    feedback: SessionFeedback | None,
    plan: PlannedSession | None,
) -> tuple[dict, list[str]]:
    flags: list[str] = []

    if feedback is None:
        return {
            "status": "missing",
            "feedback_id": None,
            "rpe": {
                "status": "missing",
                "actual": None,
                "target": None,
            },
            "leg_fatigue": {
                "status": "missing",
                "actual": None,
                "high_threshold":
                    HIGH_LEG_FATIGUE,
            },
            "comment": None,
            "comment_present": False,
            "custom_metrics": {},
        }, flags

    target, target_error = (
        _rpe_target(
            None
            if plan is None
            else plan.targets
        )
    )

    if target_error is not None:
        flags.append(
            "subjective_rpe_target_invalid"
        )

    if feedback.rpe is None:
        rpe_status = "missing"

    elif target_error is not None:
        rpe_status = "target_invalid"

    elif target is None:
        rpe_status = "recorded"

    elif feedback.rpe < target["min"]:
        rpe_status = "below_target"
        flags.append(
            "rpe_below_target"
        )

    elif feedback.rpe > target["max"]:
        rpe_status = "above_target"
        flags.append(
            "rpe_above_target"
        )

    else:
        rpe_status = "aligned"

    if feedback.leg_fatigue is None:
        leg_status = "missing"

    elif (
        feedback.leg_fatigue
        >= HIGH_LEG_FATIGUE
    ):
        leg_status = "high"
        flags.append(
            "high_leg_fatigue"
        )

    else:
        leg_status = "recorded"

    comment_present = bool(
        feedback.comment
        and feedback.comment.strip()
    )

    return {
        "status": "available",
        "feedback_id":
            str(feedback.id),
        "rpe": {
            "status":
                rpe_status,
            "actual":
                feedback.rpe,
            "target":
                target,
        },
        "leg_fatigue": {
            "status":
                leg_status,
            "actual":
                feedback.leg_fatigue,
            "high_threshold":
                HIGH_LEG_FATIGUE,
        },
        "comment":
            feedback.comment,
        "comment_present":
            comment_present,

        # Athlete-specific data passes through,
        # but core rules deliberately do not
        # interpret it.
        "custom_metrics":
            feedback.custom_metrics
            or {},
    }, flags


def _setup_assessment(
    planned_setup_id:
        uuid.UUID | None,
    actual_setup_id:
        uuid.UUID | None,
) -> dict:
    planned = (
        None
        if planned_setup_id is None
        else str(planned_setup_id)
    )

    actual = (
        None
        if actual_setup_id is None
        else str(actual_setup_id)
    )

    if planned_setup_id is None:
        status = "not_specified"
    elif actual_setup_id is None:
        status = "actual_missing"
    elif planned_setup_id == actual_setup_id:
        status = "matched"
    else:
        status = "changed"

    return {
        "status": status,
        "planned_training_setup_id":
            planned,
        "actual_training_setup_id":
            actual,
    }


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
            "feedback_available": 0,
            "feedback_missing": 0,
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

            subjective_status = (
                payload["evidence"][
                    "subjective_response"
                ]["status"]
            )

            result[
                f"feedback_{subjective_status}"
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

    def _training_setup_evidence(
        self,
        athlete_id: uuid.UUID,
        canonical: CanonicalSession,
    ) -> tuple[dict, list[str]]:
        flags: list[str] = []

        if canonical.training_setup_id is None:
            return {
                "status": "missing",
                "training_setup_id": None,
                "environment": None,
                "discipline": None,
                "bike_id": None,
                "primary_power_source_id":
                    None,
                "secondary_power_source_id":
                    None,
            }, flags

        try:
            setup = TrainingSetupService(
                self.db
            ).get(
                athlete_id,
                canonical.training_setup_id,
            )
        except LookupError:
            flags.append(
                "training_setup_invalid"
            )

            return {
                "status": "invalid",
                "training_setup_id":
                    str(
                        canonical.training_setup_id
                    ),
                "environment": None,
                "discipline": None,
                "bike_id": None,
                "primary_power_source_id":
                    None,
                "secondary_power_source_id":
                    None,
            }, flags

        expected_environment = None

        if canonical.indoor is True:
            expected_environment = "indoor"
        elif canonical.indoor is False:
            expected_environment = "outdoor"

        if (
            expected_environment is not None
            and expected_environment
            != setup["environment"]
        ):
            flags.append(
                "training_setup_environment_conflict"
            )

        primary = setup[
            "device_roles"
        ].get(
            "primary_power_source"
        )

        secondary = setup[
            "device_roles"
        ].get(
            "secondary_power_source"
        )

        return {
            "status": "available",
            "training_setup_id":
                str(setup["id"]),
            "name": setup["name"],
            "environment":
                setup["environment"],
            "discipline":
                setup["discipline"],
            "bike_id":
                str(setup["bike"]["id"]),
            "primary_power_source_id":
                (
                    None
                    if primary is None
                    else str(primary["id"])
                ),
            "secondary_power_source_id":
                (
                    None
                    if secondary is None
                    else str(secondary["id"])
                ),
        }, flags

    def _effective_metric_profile(
        self,
        *,
        athlete_id: uuid.UUID,
        sport: str,
        environment: str,
        discipline: str | None,
        power_source_id:
            uuid.UUID | None,
        at,
        metric: str,
    ) -> tuple[dict | None, str]:
        service = PerformanceProfileService(
            self.db
        )

        candidates: list[
            tuple[
                str,
                str | None,
                uuid.UUID | None,
            ]
        ] = []

        if metric == "power":
            if power_source_id is not None:
                if discipline is not None:
                    candidates.append(
                        (
                            "source_discipline",
                            discipline,
                            power_source_id,
                        )
                    )

                candidates.append(
                    (
                        "source_generic",
                        None,
                        power_source_id,
                    )
                )

            else:
                if discipline is not None:
                    candidates.append(
                        (
                            "discipline_generic",
                            discipline,
                            None,
                        )
                    )

                candidates.append(
                    (
                        "environment_generic",
                        None,
                        None,
                    )
                )

            required_field = "ftp_w"

        elif metric == "hr":
            if discipline is not None:
                candidates.append(
                    (
                        "discipline_generic",
                        discipline,
                        None,
                    )
                )

            candidates.append(
                (
                    "environment_generic",
                    None,
                    None,
                )
            )

            required_field = (
                "threshold_hr_bpm"
            )

        else:
            raise ValueError(
                "Unsupported performance metric"
            )

        seen: set[
            tuple[
                str | None,
                uuid.UUID | None,
            ]
        ] = set()

        for (
            resolution,
            candidate_discipline,
            candidate_source,
        ) in candidates:
            key = (
                candidate_discipline,
                candidate_source,
            )

            if key in seen:
                continue

            seen.add(key)

            zone_set = (
                service.effective_zone_set(
                    athlete_id=athlete_id,
                    sport=sport,
                    environment=environment,
                    discipline=
                        candidate_discipline,
                    power_source_id=
                        candidate_source,
                    at=at,
                )
            )

            if (
                zone_set is not None
                and zone_set.get(
                    required_field
                ) is not None
            ):
                return (
                    zone_set,
                    resolution,
                )

        return None, "missing"

    @staticmethod
    def _metric_profile_evidence(
        zone_set: dict | None,
        resolution: str,
    ) -> dict:
        if zone_set is None:
            return {
                "status": "missing",
                "resolution":
                    resolution,
                "zone_set_id": None,
                "sport_profile_id":
                    None,
                "effective_from": None,
                "discipline": None,
                "power_source_id":
                    None,
            }

        return {
            "status": "available",
            "resolution":
                resolution,
            "zone_set_id":
                str(zone_set["id"]),
            "sport_profile_id":
                str(
                    zone_set[
                        "sport_profile_id"
                    ]
                ),
            "effective_from":
                zone_set[
                    "effective_from"
                ].isoformat(),
            "discipline":
                zone_set[
                    "discipline"
                ],
            "power_source_id":
                (
                    None
                    if zone_set[
                        "power_source_id"
                    ] is None
                    else str(
                        zone_set[
                            "power_source_id"
                        ]
                    )
                ),
        }

    def _performance_evidence(
        self,
        athlete_id: uuid.UUID,
        canonical: CanonicalSession,
        training_setup: dict,
    ) -> tuple[dict, list[str]]:
        flags: list[str] = []

        discipline = None
        power_source_id = None

        if (
            training_setup["status"]
            == "available"
        ):
            context = training_setup[
                "environment"
            ]

            context_source = (
                "training_setup"
            )

            discipline = training_setup[
                "discipline"
            ]

            raw_power_source = (
                training_setup[
                    "primary_power_source_id"
                ]
            )

            if raw_power_source is not None:
                power_source_id = uuid.UUID(
                    raw_power_source
                )

        elif canonical.indoor is True:
            context = "indoor"
            context_source = (
                "canonical_indoor"
            )

        elif canonical.indoor is False:
            context = "outdoor"
            context_source = (
                "canonical_indoor"
            )

        else:
            context = None
            context_source = None

        base = {
            "context": context,
            "environment": context,
            "context_source":
                context_source,
            "discipline":
                discipline,
            "power_source_id":
                (
                    None
                    if power_source_id is None
                    else str(
                        power_source_id
                    )
                ),
        }

        if context is None:
            flags.append(
                "performance_context_unknown"
            )

            return {
                "status":
                    "context_unknown",
                **base,
                "zone_set_id": None,
                "effective_from": None,
                "power_profile":
                    self._metric_profile_evidence(
                        None,
                        "missing",
                    ),
                "hr_profile":
                    self._metric_profile_evidence(
                        None,
                        "missing",
                    ),
                "ftp_w": None,
                "threshold_hr_bpm": None,
                "avg_power_pct_ftp": None,
                "normalized_power_pct_ftp":
                    None,
                "intensity_factor": None,
                "avg_hr_pct_threshold": None,
                "max_hr_pct_threshold": None,
            }, flags

        power_zone_set, power_resolution = (
            self._effective_metric_profile(
                athlete_id=athlete_id,
                sport=canonical.sport,
                environment=context,
                discipline=discipline,
                power_source_id=
                    power_source_id,
                at=canonical.start_at,
                metric="power",
            )
        )

        hr_zone_set, hr_resolution = (
            self._effective_metric_profile(
                athlete_id=athlete_id,
                sport=canonical.sport,
                environment=context,
                discipline=discipline,
                power_source_id=None,
                at=canonical.start_at,
                metric="hr",
            )
        )

        has_power_data = any(
            value is not None
            for value in (
                canonical.avg_power_w,
                canonical.normalized_power_w,
            )
        )

        has_hr_data = any(
            value is not None
            for value in (
                canonical.avg_hr_bpm,
                canonical.max_hr_bpm,
            )
        )

        if (
            has_power_data
            and power_zone_set is None
        ):
            flags.append(
                "no_effective_power_profile"
            )

        if (
            has_hr_data
            and hr_zone_set is None
        ):
            flags.append(
                "no_effective_hr_profile"
            )

        if (
            power_zone_set is None
            and hr_zone_set is None
        ):
            flags.append(
                "no_effective_zone_set"
            )

        power_missing = (
            has_power_data
            and power_zone_set is None
        )

        hr_missing = (
            has_hr_data
            and hr_zone_set is None
        )

        if (
            power_zone_set is None
            and hr_zone_set is None
        ):
            status = "zone_set_missing"

        elif (
            power_missing
            or hr_missing
        ):
            status = "partial"

        else:
            status = "available"

        ftp_w = (
            None
            if power_zone_set is None
            else power_zone_set["ftp_w"]
        )

        threshold_hr = (
            None
            if hr_zone_set is None
            else hr_zone_set[
                "threshold_hr_bpm"
            ]
        )

        power_profile = (
            self._metric_profile_evidence(
                power_zone_set,
                power_resolution,
            )
        )

        hr_profile = (
            self._metric_profile_evidence(
                hr_zone_set,
                hr_resolution,
            )
        )

        power_zone_id = (
            None
            if power_zone_set is None
            else power_zone_set["id"]
        )

        hr_zone_id = (
            None
            if hr_zone_set is None
            else hr_zone_set["id"]
        )

        # Legacy field is only safe when
        # both metrics come from one zone set,
        # or only one profile exists.
        if (
            power_zone_id is not None
            and hr_zone_id is not None
            and power_zone_id != hr_zone_id
        ):
            legacy_zone_set_id = None

        else:
            legacy_id = (
                power_zone_id
                if power_zone_id is not None
                else hr_zone_id
            )

            legacy_zone_set_id = (
                None
                if legacy_id is None
                else str(legacy_id)
            )

        legacy_effective_from = None

        if power_zone_set is not None:
            legacy_effective_from = (
                power_zone_set[
                    "effective_from"
                ].isoformat()
            )

        elif hr_zone_set is not None:
            legacy_effective_from = (
                hr_zone_set[
                    "effective_from"
                ].isoformat()
            )

        return {
            "status": status,
            **base,
            "zone_set_id":
                legacy_zone_set_id,
            "effective_from":
                legacy_effective_from,
            "power_profile":
                power_profile,
            "hr_profile":
                hr_profile,
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
        (
            training_setup,
            training_setup_flags,
        ) = self._training_setup_evidence(
            athlete_id,
            canonical,
        )

        performance, performance_flags = (
            self._performance_evidence(
                athlete_id,
                canonical,
                training_setup,
            )
        )

        feedback = self.db.scalar(
            select(
                SessionFeedback
            ).where(
                SessionFeedback.athlete_id
                == athlete_id,
                SessionFeedback
                .canonical_session_id
                == canonical.id,
            )
        )

        (
            subjective_response,
            subjective_flags,
        ) = _subjective_response(
            feedback=feedback,
            plan=None,
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
            "training_setup_id":
                (
                    None
                    if canonical.training_setup_id
                    is None
                    else str(
                        canonical.training_setup_id
                    )
                ),
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
                    *training_setup_flags,
                    *performance_flags,
                    *subjective_flags,
                ],
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                    "training_setup":
                        training_setup,
                    "subjective_response":
                        subjective_response,
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
                    *training_setup_flags,
                    *performance_flags,
                    *subjective_flags,
                ],
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                    "training_setup":
                        training_setup,
                    "subjective_response":
                        subjective_response,
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
                    *training_setup_flags,
                    *performance_flags,
                    *subjective_flags,
                ],
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                    "training_setup":
                        training_setup,
                    "subjective_response":
                        subjective_response,
                },
            }

        (
            subjective_response,
            subjective_flags,
        ) = _subjective_response(
            feedback=feedback,
            plan=plan,
        )

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
            *training_setup_flags,
            *performance_flags,
            *stimulus_flags,
            *subjective_flags,
        ]

        setup_assessment = (
            _setup_assessment(
                plan.training_setup_id,
                canonical.training_setup_id,
            )
        )

        if (
            setup_assessment["status"]
            == "actual_missing"
        ):
            flags.append(
                "training_setup_actual_missing"
            )

        elif (
            setup_assessment["status"]
            == "changed"
        ):
            flags.append(
                "training_setup_changed"
            )

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
                "training_setup":
                    training_setup,
                "subjective_response":
                    subjective_response,
                "setup_assessment":
                    setup_assessment,
                "duration_assessment":
                    duration,
                "stimulus_assessment":
                    stimulus,
                "planned": {
                    "duration_s":
                        plan.planned_duration_s,
                    "training_setup_id":
                        (
                            None
                            if plan.training_setup_id
                            is None
                            else str(
                                plan.training_setup_id
                            )
                        ),
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

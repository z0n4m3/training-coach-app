from __future__ import annotations

import uuid

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


ANALYSIS_VERSION = "deterministic-v2"

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
        "ratio": round(
            float(actual / planned),
            6,
        ),
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
            "on_plan": 0,
            "modified_minor": 0,
            "modified_major": 0,
            "unplanned": 0,
            "matched_no_comparable_targets": 0,
            "match_conflict": 0,
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
                payload[
                    "planned_session_id"
                ]
            )
            analysis.analysis_version = (
                ANALYSIS_VERSION
            )
            analysis.classification = (
                payload[
                    "classification"
                ]
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
                "status": "context_unknown",
                "context": None,
                "zone_set_id": None,
                "ftp_w": None,
                "threshold_hr_bpm": None,
                "avg_power_pct_ftp": None,
                "normalized_power_pct_ftp": None,
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
                "status": "zone_set_missing",
                "context": context,
                "zone_set_id": None,
                "ftp_w": None,
                "threshold_hr_bpm": None,
                "avg_power_pct_ftp": None,
                "normalized_power_pct_ftp": None,
                "intensity_factor": None,
                "avg_hr_pct_threshold": None,
                "max_hr_pct_threshold": None,
            }, flags

        ftp_w = zone_set["ftp_w"]
        threshold_hr = zone_set[
            "threshold_hr_bpm"
        ]

        intensity_factor = _ratio(
            canonical.normalized_power_w,
            ftp_w,
        )

        evidence = {
            "status": "available",
            "context": context,
            "zone_set_id": str(
                zone_set["id"]
            ),
            "effective_from": (
                zone_set[
                    "effective_from"
                ].isoformat()
            ),
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
                intensity_factor,
            "intensity_factor_basis": (
                "normalized_power_w/ftp_w"
                if intensity_factor
                is not None
                else None
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
        }

        return evidence, flags

    def _analyze_one(
        self,
        athlete_id: uuid.UUID,
        canonical: CanonicalSession,
    ) -> dict:
        performance, performance_flags = (
            self._performance_evidence(
                athlete_id=athlete_id,
                canonical=canonical,
            )
        )

        matches = self.db.scalars(
            select(SessionMatch)
            .where(
                SessionMatch.athlete_id
                == athlete_id,
                SessionMatch.canonical_session_id
                == canonical.id,
            )
            .order_by(
                SessionMatch.created_at.asc()
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
                "classification": "unplanned",
                "flags": (
                    [
                        "no_planned_session_match"
                    ]
                    + performance_flags
                ),
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
                "flags": (
                    [
                        "multiple_plan_matches"
                    ]
                    + performance_flags
                ),
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                    "match_count":
                        len(matches),
                    "planned_session_ids": [
                        str(
                            match.planned_session_id
                        )
                        for match in matches
                    ],
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
                "flags": (
                    [
                        "invalid_plan_match"
                    ]
                    + performance_flags
                ),
                "evidence": {
                    "actual": actual,
                    "performance":
                        performance,
                    "match_count": 1,
                    "planned_session_id":
                        str(
                            match.planned_session_id
                        ),
                },
            }

        comparisons = {
            "duration": _comparison(
                canonical.duration_s,
                plan.planned_duration_s,
            ),
            "distance": _comparison(
                canonical.distance_m,
                plan.planned_distance_m,
            ),
        }

        available = {
            key: value
            for key, value
            in comparisons.items()
            if value is not None
        }

        flags: list[str] = list(
            performance_flags
        )

        for (
            metric,
            comparison,
        ) in available.items():
            if (
                comparison["level"]
                == "within"
            ):
                continue

            flags.append(
                (
                    f"{metric}_"
                    f"{comparison['direction']}_"
                    f"{comparison['level']}"
                )
            )

        if not available:
            classification = (
                "matched_no_comparable_targets"
            )
        elif any(
            comparison["level"] == "major"
            for comparison
            in available.values()
        ):
            classification = (
                "modified_major"
            )
        elif any(
            comparison["level"] == "minor"
            for comparison
            in available.values()
        ):
            classification = (
                "modified_minor"
            )
        else:
            classification = "on_plan"

        return {
            "planned_session_id": plan.id,
            "classification":
                classification,
            "flags": flags,
            "evidence": {
                "actual": actual,
                "performance":
                    performance,
                "planned": {
                    "duration_s":
                        plan.planned_duration_s,
                    "distance_m":
                        plan.planned_distance_m,
                    "session_type":
                        plan.session_type,
                    "priority":
                        plan.priority,
                    "targets":
                        plan.targets,
                },
                "comparisons":
                    comparisons,
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

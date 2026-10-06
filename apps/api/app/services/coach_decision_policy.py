from __future__ import annotations

from typing import Any


DECISION_VERSION = (
    "weekly-decision-v1"
)


# These are versioned product-policy
# thresholds, not universal physiology
# constants.
#
# They are deliberately conservative
# until real athlete history,
# durability, decoupling and wellness
# evidence are available.

REBUILD_VOLUME_THRESHOLD = 0.50
REBUILD_ACTUAL_WEEK_MAX = 0.65

HOLD_VOLUME_THRESHOLD = 0.85

REDIRECT_ACTUAL_WEEK_MIN = 0.80
REDIRECT_UNPLANNED_SHARE = 0.30
REDIRECT_MIN_UNPLANNED_S = 1800
REDIRECT_STIMULUS_DEVIATION = 0.50

OVERLOAD_RATIO = 1.20
RECOVER_OVERLOAD_RATIO = 1.25

PROGRESS_VOLUME_MIN = 0.90
PROGRESS_MATCHED_DURATION_MIN = 0.90
PROGRESS_MATCHED_DURATION_MAX = 1.10
PROGRESS_ACTUAL_WEEK_MAX = 1.15
PROGRESS_UNPLANNED_SHARE_MAX = 0.15
PROGRESS_ANALYSIS_COVERAGE_MIN = 0.75
PROGRESS_FEEDBACK_COVERAGE_MIN = 0.50
PROGRESS_STIMULUS_ALIGNED_MIN = 0.67
PROGRESS_STIMULUS_DEVIATION_MAX = 0.33
PROGRESS_MIN_COMPARABLE_STIMULUS = 2
PROGRESS_MAJOR_DURATION_DEVIATION_MAX = 0.20

MIN_PLANNED_DURATION_COVERAGE = 0.75


def _number(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _int(
    value: Any,
) -> int:
    number = _number(
        value
    )

    if number is None:
        return 0

    return int(number)


def _gte(
    value: float | None,
    threshold: float,
) -> bool:
    return (
        value is not None
        and value >= threshold
    )


def _gt(
    value: float | None,
    threshold: float,
) -> bool:
    return (
        value is not None
        and value > threshold
    )


def _lt(
    value: float | None,
    threshold: float,
) -> bool:
    return (
        value is not None
        and value < threshold
    )


def _between(
    value: float | None,
    low: float,
    high: float,
) -> bool:
    return (
        value is not None
        and low <= value <= high
    )


def _priority(
    execution: dict,
    name: str,
) -> dict:
    value = execution.get(
        name,
        {}
    )

    if not isinstance(
        value,
        dict,
    ):
        return {}

    return value


def _confidence(
    *,
    planned_duration_coverage:
        float | None,
    analysis_coverage:
        float | None,
    feedback_coverage:
        float | None,
) -> str:
    if (
        _gte(
            planned_duration_coverage,
            0.99,
        )
        and _gte(
            analysis_coverage,
            0.80,
        )
        and _gte(
            feedback_coverage,
            0.60,
        )
    ):
        return "high"

    if (
        _gte(
            planned_duration_coverage,
            0.75,
        )
        and _gte(
            analysis_coverage,
            0.50,
        )
    ):
        return "medium"

    return "low"


def evaluate_weekly_decision(
    coach_kpis: dict,
) -> dict:
    """
    Convert deterministic Weekly Review
    KPIs into a coaching direction.

    This function:
    - does not modify the plan,
    - does not publish to Intervals,
    - does not use distance as compliance,
    - does not penalize weekday shifts,
    - does not pretend durability or
      decoupling exist when unavailable.
    """

    execution = (
        coach_kpis.get(
            "execution",
            {}
        )
        or {}
    )

    load = (
        coach_kpis.get(
            "load",
            {}
        )
        or {}
    )

    stimulus = (
        coach_kpis.get(
            "stimulus",
            {}
        )
        or {}
    )

    duration = (
        coach_kpis.get(
            "duration_execution",
            {}
        )
        or {}
    )

    subjective = (
        coach_kpis.get(
            "subjective_response",
            {}
        )
        or {}
    )

    readiness = (
        coach_kpis.get(
            "data_readiness",
            {}
        )
        or {}
    )

    key = _priority(
        execution,
        "KEY",
    )

    support = _priority(
        execution,
        "SUPPORT",
    )

    easy = _priority(
        execution,
        "EASY",
    )

    planned_count = (
        _int(
            key.get(
                "planned_session_count"
            )
        )
        + _int(
            support.get(
                "planned_session_count"
            )
        )
        + _int(
            easy.get(
                "planned_session_count"
            )
        )
    )

    volume_completion = _number(
        execution.get(
            "planned_volume_completion_ratio"
        )
    )

    matched_duration_ratio = _number(
        execution.get(
            "matched_actual_vs_planned_duration_ratio"
        )
    )

    key_planned = _int(
        key.get(
            "planned_session_count"
        )
    )

    key_completion = _number(
        key.get(
            "session_completion_ratio"
        )
    )

    actual_week_ratio = _number(
        load.get(
            "actual_week_vs_planned_duration_ratio"
        )
    )

    unplanned_share = _number(
        load.get(
            "unplanned_duration_share"
        )
    )

    unplanned_duration_s = _number(
        load.get(
            "unplanned_duration_s"
        )
    ) or 0.0

    comparable_stimulus = _int(
        stimulus.get(
            "comparable_session_count"
        )
    )

    aligned_ratio = _number(
        stimulus.get(
            "aligned_ratio"
        )
    )

    stimulus_deviation_ratio = _number(
        stimulus.get(
            "deviation_ratio"
        )
    )

    duration_major_ratio = _number(
        duration.get(
            "major_deviation_ratio"
        )
    )

    high_leg_fatigue_count = _int(
        subjective.get(
            "high_leg_fatigue_count"
        )
    )

    rpe_above_target_count = _int(
        subjective.get(
            "rpe_above_target_count"
        )
    )

    feedback_coverage = _number(
        subjective.get(
            "feedback_coverage"
        )
    )

    analysis_coverage = _number(
        readiness.get(
            "analysis_coverage"
        )
    )

    planned_duration_coverage = _number(
        readiness.get(
            "planned_duration_coverage"
        )
    )

    confidence = _confidence(
        planned_duration_coverage=
            planned_duration_coverage,
        analysis_coverage=
            analysis_coverage,
        feedback_coverage=
            feedback_coverage,
    )

    evidence = {
        "planned_session_count":
            planned_count,

        "planned_volume_completion_ratio":
            volume_completion,

        "matched_actual_vs_planned_duration_ratio":
            matched_duration_ratio,

        "key_planned_session_count":
            key_planned,

        "key_session_completion_ratio":
            key_completion,

        "actual_week_vs_planned_duration_ratio":
            actual_week_ratio,

        "unplanned_duration_share":
            unplanned_share,

        "unplanned_duration_s":
            unplanned_duration_s,

        "comparable_stimulus_session_count":
            comparable_stimulus,

        "stimulus_aligned_ratio":
            aligned_ratio,

        "stimulus_deviation_ratio":
            stimulus_deviation_ratio,

        "major_duration_deviation_ratio":
            duration_major_ratio,

        "high_leg_fatigue_count":
            high_leg_fatigue_count,

        "rpe_above_target_count":
            rpe_above_target_count,

        "analysis_coverage":
            analysis_coverage,

        "feedback_coverage":
            feedback_coverage,

        "planned_duration_coverage":
            planned_duration_coverage,
    }

    base = {
        "decision_version":
            DECISION_VERSION,

        "confidence":
            confidence,

        "evidence":
            evidence,

        "constraints": {
            "automatic_plan_change":
                False,

            "requires_athlete_approval_for_plan_change":
                True,

            "weekday_shift_penalizes_compliance":
                False,

            "distance_used_for_compliance":
                False,
        },
    }

    period_status = (
        coach_kpis.get(
            "period_status"
        )
    )

    if period_status != "complete":
        return {
            **base,
            "status":
                "not_ready",
            "decision":
                None,
            "selected_rule":
                "week_not_complete",
            "reasons": [
                "training_week_not_complete",
            ],
        }

    if planned_count <= 0:
        return {
            **base,
            "status":
                "not_ready",
            "decision":
                None,
            "selected_rule":
                "plan_missing",
            "reasons": [
                "no_planned_sessions",
            ],
        }

    if (
        planned_duration_coverage
        is None
        or planned_duration_coverage
        < MIN_PLANNED_DURATION_COVERAGE
        or volume_completion
        is None
    ):
        return {
            **base,
            "status":
                "not_ready",
            "decision":
                None,
            "selected_rule":
                "planned_volume_data_missing",
            "reasons": [
                "insufficient_planned_duration_data",
            ],
        }

    # --------------------------------
    # REBUILD
    # --------------------------------
    #
    # Large interruption in execution.
    # This says "re-establish training
    # continuity", not "fitness is lost".

    if (
        volume_completion
        < REBUILD_VOLUME_THRESHOLD
        and _lt(
            actual_week_ratio,
            REBUILD_ACTUAL_WEEK_MAX,
        )
    ):
        return {
            **base,
            "status":
                "ready",
            "decision":
                "REBUILD",
            "selected_rule":
                "major_execution_gap",
            "reasons": [
                "planned_volume_severely_undercompleted",
            ],
        }

    if (
        key_planned > 0
        and key_completion == 0
        and volume_completion < 0.65
        and _lt(
            actual_week_ratio,
            REBUILD_ACTUAL_WEEK_MAX,
        )
    ):
        return {
            **base,
            "status":
                "ready",
            "decision":
                "REBUILD",
            "selected_rule":
                "key_and_volume_interruption",
            "reasons": [
                "key_sessions_not_completed",
                "planned_volume_materially_undercompleted",
            ],
        }

    # --------------------------------
    # RECOVER
    # --------------------------------

    strong_fatigue_signal = (
        high_leg_fatigue_count >= 2
        or (
            high_leg_fatigue_count >= 1
            and rpe_above_target_count >= 1
            and _gte(
                feedback_coverage,
                0.50,
            )
        )
    )

    overload_with_fatigue = (
        _gt(
            actual_week_ratio,
            RECOVER_OVERLOAD_RATIO,
        )
        and high_leg_fatigue_count >= 1
    )

    if (
        strong_fatigue_signal
        or overload_with_fatigue
    ):
        reasons = []

        if strong_fatigue_signal:
            reasons.append(
                "strong_subjective_fatigue_signal"
            )

        if overload_with_fatigue:
            reasons.append(
                "high_week_volume_with_fatigue"
            )

        return {
            **base,
            "status":
                "ready",
            "decision":
                "RECOVER",
            "selected_rule":
                "recovery_signal",
            "reasons":
                reasons,
        }

    # --------------------------------
    # REDIRECT
    # --------------------------------
    #
    # Volume may be reasonably executed,
    # but the training being performed is
    # materially different from the plan.

    repeated_stimulus_mismatch = (
        volume_completion >= 0.80
        and comparable_stimulus >= 2
        and _gte(
            stimulus_deviation_ratio,
            REDIRECT_STIMULUS_DEVIATION,
        )
    )

    material_unplanned_training = (
        _gte(
            actual_week_ratio,
            REDIRECT_ACTUAL_WEEK_MIN,
        )
        and _gte(
            unplanned_share,
            REDIRECT_UNPLANNED_SHARE,
        )
        and (
            unplanned_duration_s
            >= REDIRECT_MIN_UNPLANNED_S
        )
    )

    if (
        repeated_stimulus_mismatch
        or material_unplanned_training
    ):
        reasons = []

        if repeated_stimulus_mismatch:
            reasons.append(
                "repeated_stimulus_mismatch"
            )

        if material_unplanned_training:
            reasons.append(
                "material_unplanned_training_share"
            )

        return {
            **base,
            "status":
                "ready",
            "decision":
                "REDIRECT",
            "selected_rule":
                "training_direction_mismatch",
            "reasons":
                reasons,
        }

    # --------------------------------
    # HOLD
    # --------------------------------

    hold_reasons = []

    if (
        volume_completion
        < HOLD_VOLUME_THRESHOLD
    ):
        hold_reasons.append(
            "planned_volume_undercompleted"
        )

    if (
        key_planned > 0
        and (
            key_completion is None
            or key_completion < 1.0
        )
    ):
        hold_reasons.append(
            "key_session_execution_incomplete"
        )

    if _gt(
        actual_week_ratio,
        OVERLOAD_RATIO,
    ):
        hold_reasons.append(
            "actual_week_volume_above_plan"
        )

    if (
        matched_duration_ratio
        is not None
        and (
            matched_duration_ratio < 0.80
            or matched_duration_ratio > 1.20
        )
    ):
        hold_reasons.append(
            "matched_session_duration_materially_differs_from_plan"
        )

    mild_fatigue_signal = (
        high_leg_fatigue_count >= 1
        or rpe_above_target_count >= 1
    )

    if mild_fatigue_signal:
        hold_reasons.append(
            "subjective_load_signal_present"
        )

    if hold_reasons:
        return {
            **base,
            "status":
                "ready",
            "decision":
                "HOLD",
            "selected_rule":
                "progression_not_supported",
            "reasons":
                hold_reasons,
        }

    # --------------------------------
    # PROGRESS
    # --------------------------------

    key_ready = (
        key_planned == 0
        or key_completion == 1.0
    )

    duration_quality_ok = (
        duration_major_ratio is None
        or (
            duration_major_ratio
            <= PROGRESS_MAJOR_DURATION_DEVIATION_MAX
        )
    )

    progress_supported = (
        volume_completion
        >= PROGRESS_VOLUME_MIN

        and key_ready

        and _between(
            matched_duration_ratio,
            PROGRESS_MATCHED_DURATION_MIN,
            PROGRESS_MATCHED_DURATION_MAX,
        )

        and (
            actual_week_ratio is None
            or actual_week_ratio
            <= PROGRESS_ACTUAL_WEEK_MAX
        )

        and (
            unplanned_share is None
            or unplanned_share
            <= PROGRESS_UNPLANNED_SHARE_MAX
        )

        and _gte(
            analysis_coverage,
            PROGRESS_ANALYSIS_COVERAGE_MIN,
        )

        and _gte(
            feedback_coverage,
            PROGRESS_FEEDBACK_COVERAGE_MIN,
        )

        and comparable_stimulus
        >= PROGRESS_MIN_COMPARABLE_STIMULUS

        and _gte(
            aligned_ratio,
            PROGRESS_STIMULUS_ALIGNED_MIN,
        )

        and (
            stimulus_deviation_ratio
            is not None
            and stimulus_deviation_ratio
            <= PROGRESS_STIMULUS_DEVIATION_MAX
        )

        and duration_quality_ok

        and high_leg_fatigue_count == 0

        and rpe_above_target_count == 0
    )

    if (
        progress_supported
        and confidence
        in {
            "high",
            "medium",
        }
    ):
        return {
            **base,
            "status":
                "ready",
            "decision":
                "PROGRESS",
            "selected_rule":
                "progression_supported",
            "reasons": [
                "planned_volume_completed",
                "key_sessions_completed",
                "stimulus_generally_aligned",
                "no_material_subjective_overload_signal",
            ],
        }

    # --------------------------------
    # CONTINUE
    # --------------------------------
    #
    # Default conservative outcome:
    # no strong reason to regress,
    # redirect or progress.

    reasons = [
        "no_major_negative_signal",
        "evidence_not_strong_enough_for_progression",
    ]

    if (
        comparable_stimulus
        < PROGRESS_MIN_COMPARABLE_STIMULUS
    ):
        reasons.append(
            "limited_comparable_stimulus_evidence"
        )

    if (
        analysis_coverage is None
        or analysis_coverage
        < PROGRESS_ANALYSIS_COVERAGE_MIN
    ):
        reasons.append(
            "analysis_coverage_limits_progression_confidence"
        )

    if (
        feedback_coverage is None
        or feedback_coverage
        < PROGRESS_FEEDBACK_COVERAGE_MIN
    ):
        reasons.append(
            "feedback_coverage_limits_progression_confidence"
        )

    return {
        **base,
        "status":
            "ready",
        "decision":
            "CONTINUE",
        "selected_rule":
            "conservative_default",
        "reasons":
            reasons,
    }

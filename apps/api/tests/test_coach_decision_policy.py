from copy import deepcopy

from app.services.coach_decision_policy import (
    evaluate_weekly_decision,
)


def good_week() -> dict:
    return {
        "schema_version":
            "weekly-kpi-v1",

        "period_status":
            "complete",

        "execution": {
            "session_completion_ratio":
                1.0,

            "planned_volume_completion_ratio":
                1.0,

            "matched_actual_vs_planned_duration_ratio":
                1.0,

            "KEY": {
                "planned_session_count":
                    2,
                "matched_session_count":
                    2,
                "session_completion_ratio":
                    1.0,
                "planned_volume_completion_ratio":
                    1.0,
            },

            "SUPPORT": {
                "planned_session_count":
                    2,
                "matched_session_count":
                    2,
                "session_completion_ratio":
                    1.0,
                "planned_volume_completion_ratio":
                    1.0,
            },

            "EASY": {
                "planned_session_count":
                    1,
                "matched_session_count":
                    1,
                "session_completion_ratio":
                    1.0,
                "planned_volume_completion_ratio":
                    1.0,
            },
        },

        "load": {
            "planned_duration_s":
                36000,

            "actual_week_duration_s":
                36000,

            "actual_week_vs_planned_duration_ratio":
                1.0,

            "training_load":
                420,

            "work_kj":
                5200,

            "unplanned_session_count":
                0,

            "unplanned_duration_s":
                0,

            "unplanned_duration_share":
                0.0,
        },

        "stimulus": {
            "comparable_session_count":
                3,

            "aligned_count":
                3,

            "above_target_count":
                0,

            "below_target_count":
                0,

            "mixed_count":
                0,

            "aligned_ratio":
                1.0,

            "deviation_ratio":
                0.0,

            "interval_analysis_required_count":
                1,

            "not_evaluable_count":
                1,
        },

        "duration_execution": {
            "comparable_session_count":
                4,

            "within_count":
                4,

            "minor_deviation_count":
                0,

            "major_deviation_count":
                0,

            "within_ratio":
                1.0,

            "major_deviation_ratio":
                0.0,
        },

        "subjective_response": {
            "feedback_coverage":
                0.8,

            "rpe_above_target_count":
                0,

            "rpe_below_target_count":
                0,

            "high_leg_fatigue_count":
                0,

            "rpe_avg_descriptive":
                4.0,

            "leg_fatigue_avg_descriptive":
                2.0,
        },

        "data_readiness": {
            "analysis_coverage":
                1.0,

            "feedback_coverage":
                0.8,

            "planned_duration_coverage":
                1.0,

            "training_load_coverage":
                1.0,

            "work_kj_coverage":
                0.8,
        },

        "schedule_context": {
            "shifted_session_count":
                2,

            "max_abs_shift_days":
                2,

            "weekday_shift_penalizes_compliance":
                False,
        },

        "advanced_endurance": {
            "durability": {
                "status":
                    "not_available_in_current_analysis",
            },

            "decoupling": {
                "status":
                    "not_available_in_current_analysis",
            },
        },
    }


def test_progress_requires_strong_evidence():
    result = evaluate_weekly_decision(
        good_week()
    )

    assert result["status"] == "ready"
    assert result["decision"] == "PROGRESS"
    assert (
        result["selected_rule"]
        == "progression_supported"
    )

    assert (
        result["constraints"][
            "automatic_plan_change"
        ]
        is False
    )

    assert (
        result["constraints"][
            "requires_athlete_approval_for_plan_change"
        ]
        is True
    )


def test_continue_when_week_is_good_but_evidence_is_limited():
    kpis = good_week()

    kpis["stimulus"][
        "comparable_session_count"
    ] = 1

    kpis["stimulus"][
        "aligned_count"
    ] = 1

    kpis["stimulus"][
        "aligned_ratio"
    ] = 1.0

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["decision"] == "CONTINUE"

    assert (
        "limited_comparable_stimulus_evidence"
        in result["reasons"]
    )


def test_hold_after_material_undercompletion():
    kpis = good_week()

    kpis["execution"][
        "planned_volume_completion_ratio"
    ] = 0.72

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["decision"] == "HOLD"

    assert (
        "planned_volume_undercompleted"
        in result["reasons"]
    )


def test_rebuild_after_major_training_interruption():
    kpis = good_week()

    kpis["execution"][
        "planned_volume_completion_ratio"
    ] = 0.40

    kpis["execution"]["KEY"][
        "session_completion_ratio"
    ] = 0.0

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["decision"] == "REBUILD"

    assert (
        result["selected_rule"]
        == "major_execution_gap"
    )


def test_recover_after_combined_subjective_fatigue():
    kpis = good_week()

    kpis["subjective_response"][
        "high_leg_fatigue_count"
    ] = 1

    kpis["subjective_response"][
        "rpe_above_target_count"
    ] = 1

    kpis["subjective_response"][
        "feedback_coverage"
    ] = 0.8

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["decision"] == "RECOVER"

    assert (
        "strong_subjective_fatigue_signal"
        in result["reasons"]
    )


def test_redirect_when_executed_stimulus_differs_from_plan():
    kpis = good_week()

    kpis["stimulus"][
        "comparable_session_count"
    ] = 3

    kpis["stimulus"][
        "aligned_count"
    ] = 1

    kpis["stimulus"][
        "above_target_count"
    ] = 2

    kpis["stimulus"][
        "aligned_ratio"
    ] = round(
        1 / 3,
        4,
    )

    kpis["stimulus"][
        "deviation_ratio"
    ] = round(
        2 / 3,
        4,
    )

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["decision"] == "REDIRECT"

    assert (
        "repeated_stimulus_mismatch"
        in result["reasons"]
    )


def test_redirect_after_material_unplanned_training():
    kpis = good_week()

    kpis["load"][
        "unplanned_duration_s"
    ] = 10800

    kpis["load"][
        "unplanned_duration_share"
    ] = 0.30

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["decision"] == "REDIRECT"

    assert (
        "material_unplanned_training_share"
        in result["reasons"]
    )


def test_incomplete_week_is_not_ready():
    kpis = good_week()

    kpis[
        "period_status"
    ] = "in_progress"

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["status"] == "not_ready"
    assert result["decision"] is None

    assert (
        result["selected_rule"]
        == "week_not_complete"
    )


def test_missing_plan_volume_data_is_not_ready():
    kpis = good_week()

    kpis["data_readiness"][
        "planned_duration_coverage"
    ] = 0.50

    result = evaluate_weekly_decision(
        kpis
    )

    assert result["status"] == "not_ready"
    assert result["decision"] is None


def test_weekday_shifts_do_not_change_decision():
    first = good_week()

    second = deepcopy(
        first
    )

    first["schedule_context"][
        "shifted_session_count"
    ] = 0

    first["schedule_context"][
        "max_abs_shift_days"
    ] = 0

    second["schedule_context"][
        "shifted_session_count"
    ] = 5

    second["schedule_context"][
        "max_abs_shift_days"
    ] = 5

    first_result = (
        evaluate_weekly_decision(
            first
        )
    )

    second_result = (
        evaluate_weekly_decision(
            second
        )
    )

    assert (
        first_result["decision"]
        == second_result["decision"]
        == "PROGRESS"
    )


def test_distance_is_not_a_decision_input():
    kpis = good_week()

    kpis["distance_m"] = 999999

    first = evaluate_weekly_decision(
        kpis
    )

    kpis["distance_m"] = 1

    second = evaluate_weekly_decision(
        kpis
    )

    assert (
        first["decision"]
        == second["decision"]
    )

    assert (
        first["constraints"][
            "distance_used_for_compliance"
        ]
        is False
    )

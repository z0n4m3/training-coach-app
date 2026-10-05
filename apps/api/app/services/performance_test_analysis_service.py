from __future__ import annotations

import uuid
from datetime import (
    datetime,
    timezone,
)
from statistics import (
    mean,
    stdev,
)

from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
    aliased,
)

from app.domain.cycling_equipment import (
    normalize_cycling_discipline,
    normalize_training_environment,
)
from app.models.entities import (
    Athlete,
    Device,
    PerformanceTest,
    PerformanceTestResult,
)
from app.services.performance_profile_service import (
    PerformanceProfileService,
)


class PerformanceTestAnalysisService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def compare_sources(
        self,
        *,
        athlete_id: uuid.UUID,
        source_a_id: uuid.UUID,
        source_b_id: uuid.UUID,
        environment: str | None = None,
        discipline: str | None = None,
        protocol: str | None = None,
    ) -> dict:
        self._athlete(athlete_id)

        if source_a_id == source_b_id:
            raise ValueError(
                "Source A and source B must be different"
            )

        source_a = self._power_source(
            athlete_id,
            source_a_id,
        )

        source_b = self._power_source(
            athlete_id,
            source_b_id,
        )

        normalized_environment = (
            None
            if environment is None
            else normalize_training_environment(
                environment
            )
        )

        normalized_discipline = (
            None
            if discipline is None
            else normalize_cycling_discipline(
                discipline
            )
        )

        normalized_protocol = (
            None
            if protocol is None
            else protocol.strip()
        )

        result_a = aliased(
            PerformanceTestResult
        )

        result_b = aliased(
            PerformanceTestResult
        )

        query = (
            select(
                PerformanceTest,
                result_a,
                result_b,
            )
            .join(
                result_a,
                result_a.performance_test_id
                == PerformanceTest.id,
            )
            .join(
                result_b,
                result_b.performance_test_id
                == PerformanceTest.id,
            )
            .where(
                PerformanceTest.athlete_id
                == athlete_id,
                result_a.power_source_id
                == source_a_id,
                result_b.power_source_id
                == source_b_id,
            )
        )

        if normalized_environment is not None:
            query = query.where(
                PerformanceTest.environment
                == normalized_environment
            )

        if normalized_discipline is not None:
            query = query.where(
                PerformanceTest.discipline
                == normalized_discipline
            )

        if normalized_protocol is not None:
            query = query.where(
                PerformanceTest.protocol
                == normalized_protocol
            )

        rows = self.db.execute(
            query.order_by(
                PerformanceTest.tested_at.asc()
            )
        ).all()

        observations: list[dict] = []
        groups: dict[tuple, list[dict]] = {}

        for test, row_a, row_b in rows:
            delta_w = (
                row_b.observed_power_w
                - row_a.observed_power_w
            )

            delta_pct = (
                delta_w
                / row_a.observed_power_w
                * 100
            )

            window_a = (
                row_a.measurement_window_s
            )

            window_b = (
                row_b.measurement_window_s
            )

            window_comparable = (
                window_a is not None
                and window_b is not None
                and abs(window_a - window_b)
                <= 1.0
            )

            observation = {
                "test_id":
                    test.id,
                "tested_at":
                    test.tested_at,
                "test_type":
                    test.test_type,
                "protocol":
                    test.protocol,
                "environment":
                    test.environment,
                "discipline":
                    test.discipline,
                "source_a_power_w":
                    round(
                        row_a.observed_power_w,
                        3,
                    ),
                "source_b_power_w":
                    round(
                        row_b.observed_power_w,
                        3,
                    ),
                "source_b_minus_a_w":
                    round(
                        delta_w,
                        3,
                    ),
                "source_b_vs_a_pct":
                    round(
                        delta_pct,
                        3,
                    ),
                "source_a_window_s":
                    window_a,
                "source_b_window_s":
                    window_b,
                "window_comparable":
                    window_comparable,
            }

            observations.append(
                observation
            )

            group_key = (
                test.environment,
                test.discipline,
                test.test_type,
                test.protocol,
                (
                    None
                    if window_a is None
                    else round(window_a, 3)
                ),
                (
                    None
                    if window_b is None
                    else round(window_b, 3)
                ),
            )

            groups.setdefault(
                group_key,
                [],
            ).append(
                observation
            )

        comparison_groups = []

        for group_key, items in groups.items():
            (
                group_environment,
                group_discipline,
                group_test_type,
                group_protocol,
                window_a,
                window_b,
            ) = group_key

            delta_w_values = [
                item["source_b_minus_a_w"]
                for item in items
            ]

            delta_pct_values = [
                item["source_b_vs_a_pct"]
                for item in items
            ]

            count = len(items)

            sd_pct = (
                None
                if count < 2
                else stdev(
                    delta_pct_values
                )
            )

            range_pct = (
                None
                if count < 2
                else (
                    max(delta_pct_values)
                    - min(delta_pct_values)
                )
            )

            windows_ok = all(
                item["window_comparable"]
                for item in items
            )

            if not windows_ok:
                repeatability = (
                    "not_comparable"
                )

            elif count < 2:
                repeatability = (
                    "insufficient_history"
                )

            elif count == 2:
                repeatability = (
                    "preliminary"
                )

            elif sd_pct <= 1.0:
                repeatability = (
                    "high"
                )

            elif sd_pct <= 2.0:
                repeatability = (
                    "moderate"
                )

            else:
                repeatability = (
                    "low"
                )

            comparison_groups.append(
                {
                    "environment":
                        group_environment,
                    "discipline":
                        group_discipline,
                    "test_type":
                        group_test_type,
                    "protocol":
                        group_protocol,
                    "source_a_window_s":
                        window_a,
                    "source_b_window_s":
                        window_b,
                    "paired_tests":
                        count,
                    "mean_source_b_minus_a_w":
                        round(
                            mean(
                                delta_w_values
                            ),
                            3,
                        ),
                    "mean_source_b_vs_a_pct":
                        round(
                            mean(
                                delta_pct_values
                            ),
                            3,
                        ),
                    "sd_delta_pct_points":
                        (
                            None
                            if sd_pct is None
                            else round(
                                sd_pct,
                                3,
                            )
                        ),
                    "range_delta_pct_points":
                        (
                            None
                            if range_pct is None
                            else round(
                                range_pct,
                                3,
                            )
                        ),
                    "repeatability":
                        repeatability,
                    "repeatability_rule": (
                        "Same context, protocol and "
                        "measurement windows. "
                        "<2 paired tests: insufficient; "
                        "2: preliminary; >=3: "
                        "high if SD <=1.0 percentage "
                        "point, moderate if <=2.0, "
                        "otherwise low."
                    ),
                }
            )

        return {
            "athlete_id":
                athlete_id,
            "source_a": {
                "id":
                    source_a.id,
                "name":
                    source_a.name,
                "category":
                    source_a.category,
            },
            "source_b": {
                "id":
                    source_b.id,
                "name":
                    source_b.name,
                "category":
                    source_b.category,
            },
            "paired_tests":
                len(observations),
            "observations":
                observations,
            "comparison_groups":
                comparison_groups,
            "conversion_model":
                "none",
        }

    def ftp_proposal(
        self,
        *,
        athlete_id: uuid.UUID,
        power_source_id: uuid.UUID,
        environment: str,
        discipline: str | None,
        at: datetime | None = None,
    ) -> dict:
        self._athlete(
            athlete_id
        )

        power_source = (
            self._power_source(
                athlete_id,
                power_source_id,
            )
        )

        normalized_environment = (
            normalize_training_environment(
                environment
            )
        )

        normalized_discipline = (
            None
            if discipline is None
            else normalize_cycling_discipline(
                discipline
            )
        )

        reference_at = (
            at
            if at is not None
            else datetime.now(
                timezone.utc
            )
        )

        query = (
            select(
                PerformanceTest,
                PerformanceTestResult,
            )
            .join(
                PerformanceTestResult,
                (
                    PerformanceTestResult
                    .performance_test_id
                    == PerformanceTest.id
                ),
            )
            .where(
                PerformanceTest.athlete_id
                == athlete_id,
                PerformanceTest.test_type
                == "ftp",
                PerformanceTest.environment
                == normalized_environment,
                PerformanceTestResult
                .power_source_id
                == power_source_id,
                PerformanceTestResult
                .estimated_ftp_w
                .is_not(None),
                PerformanceTest.tested_at
                <= reference_at,
            )
        )

        if normalized_discipline is None:
            query = query.where(
                PerformanceTest.discipline
                .is_(None)
            )

        else:
            query = query.where(
                PerformanceTest.discipline
                == normalized_discipline
            )

        rows = self.db.execute(
            query.order_by(
                PerformanceTest.tested_at.desc()
            )
        ).all()

        current_profile = (
            PerformanceProfileService(
                self.db
            ).effective_zone_set(
                athlete_id=athlete_id,
                sport="cycling",
                environment=
                    normalized_environment,
                discipline=
                    normalized_discipline,
                power_source_id=
                    power_source_id,
                at=reference_at,
            )
        )

        current_ftp = (
            None
            if current_profile is None
            else current_profile["ftp_w"]
        )

        current = {
            "zone_set_id":
                (
                    None
                    if current_profile is None
                    else current_profile["id"]
                ),
            "ftp_w":
                current_ftp,
            "effective_from":
                (
                    None
                    if current_profile is None
                    else current_profile[
                        "effective_from"
                    ]
                ),
        }

        if not rows:
            return {
                "status":
                    "insufficient_evidence",
                "athlete_id":
                    athlete_id,
                "power_source": {
                    "id":
                        power_source.id,
                    "name":
                        power_source.name,
                    "category":
                        power_source.category,
                },
                "environment":
                    normalized_environment,
                "discipline":
                    normalized_discipline,
                "as_of":
                    reference_at,
                "current":
                    current,
                "proposed_ftp_w":
                    None,
                "delta_w":
                    None,
                "delta_pct":
                    None,
                "confidence":
                    None,
                "evidence":
                    None,
                "requires_athlete_approval":
                    False,
                "applied":
                    False,
                "conversion_used":
                    False,
            }

        (
            latest_test,
            latest_result,
        ) = rows[0]

        proposed_ftp = float(
            latest_result.estimated_ftp_w
        )

        same_protocol_count = sum(
            1
            for test, result in rows
            if (
                test.protocol
                == latest_test.protocol
                and result.estimate_method
                == latest_result.estimate_method
                and result.measurement_window_s
                == latest_result.measurement_window_s
            )
        )

        if current_ftp is None:
            delta_w = None
            delta_pct = None
            status = "review_required"

        else:
            delta_w = (
                proposed_ftp
                - current_ftp
            )

            delta_pct = (
                delta_w
                / current_ftp
                * 100
            )

            if abs(delta_w) < 0.5:
                status = "no_change"
            else:
                status = "review_required"

        return {
            "status":
                status,
            "athlete_id":
                athlete_id,
            "power_source": {
                "id":
                    power_source.id,
                "name":
                    power_source.name,
                "category":
                    power_source.category,
            },
            "environment":
                normalized_environment,
            "discipline":
                normalized_discipline,
            "as_of":
                reference_at,
            "current":
                current,
            "proposed_ftp_w":
                round(
                    proposed_ftp,
                    3,
                ),
            "delta_w":
                (
                    None
                    if delta_w is None
                    else round(
                        delta_w,
                        3,
                    )
                ),
            "delta_pct":
                (
                    None
                    if delta_pct is None
                    else round(
                        delta_pct,
                        3,
                    )
                ),
            "confidence":
                latest_result.confidence,
            "confidence_basis":
                "latest_source_specific_test_result",
            "evidence": {
                "latest_test_id":
                    latest_test.id,
                "latest_tested_at":
                    latest_test.tested_at,
                "protocol":
                    latest_test.protocol,
                "measurement_window_s":
                    latest_result
                    .measurement_window_s,
                "observed_power_w":
                    latest_result
                    .observed_power_w,
                "estimated_ftp_w":
                    latest_result
                    .estimated_ftp_w,
                "estimate_method":
                    latest_result
                    .estimate_method,
                "same_protocol_estimate_count":
                    same_protocol_count,
                "total_source_specific_ftp_estimates":
                    len(rows),
            },
            "requires_athlete_approval":
                status
                == "review_required",
            "applied":
                False,
            "conversion_used":
                False,
        }

    def _athlete(
        self,
        athlete_id: uuid.UUID,
    ) -> Athlete:
        athlete = self.db.get(
            Athlete,
            athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
            )

        return athlete

    def _power_source(
        self,
        athlete_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> Device:
        device = self.db.scalar(
            select(Device).where(
                Device.id == source_id,
                Device.athlete_id
                == athlete_id,
            )
        )

        if device is None:
            raise LookupError(
                "Power source not found"
            )

        if device.category not in {
            "power_meter",
            "trainer",
        }:
            raise ValueError(
                "Device is not a power source"
            )

        return device

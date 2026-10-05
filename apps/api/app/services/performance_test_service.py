from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.cycling_equipment import (
    normalize_cycling_discipline,
    normalize_training_environment,
)
from app.domain.sport import normalize_sport
from app.models.entities import (
    Athlete,
    CanonicalSession,
    Device,
    PerformanceTest,
    PerformanceTestResult,
)
from app.schemas.performance_tests import (
    PerformanceTestCreate,
)
from app.services.training_setup_service import (
    TrainingSetupService,
)


class PerformanceTestService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create(
        self,
        payload: PerformanceTestCreate,
    ) -> dict:
        athlete = self.db.get(
            Athlete,
            payload.athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
            )

        sport = normalize_sport(
            payload.sport
        )

        if sport != "cycling":
            raise ValueError(
                (
                    "Performance testing currently "
                    "supports cycling only"
                )
            )

        environment = (
            normalize_training_environment(
                payload.environment
            )
        )

        discipline = (
            None
            if payload.discipline is None
            else normalize_cycling_discipline(
                payload.discipline
            )
        )

        session = None

        if (
            payload.canonical_session_id
            is not None
        ):
            session = self.db.scalar(
                select(
                    CanonicalSession
                ).where(
                    CanonicalSession.id
                    == payload.canonical_session_id,
                    CanonicalSession.athlete_id
                    == payload.athlete_id,
                )
            )

            if session is None:
                raise LookupError(
                    "Canonical session not found"
                )

            if (
                normalize_sport(
                    session.sport
                )
                != sport
            ):
                raise ValueError(
                    (
                        "Canonical session sport "
                        "does not match test sport"
                    )
                )

        resolved_setup_id = (
            payload.training_setup_id
        )

        if (
            session is not None
            and session.training_setup_id
            is not None
        ):
            if (
                resolved_setup_id is not None
                and resolved_setup_id
                != session.training_setup_id
            ):
                raise ValueError(
                    (
                        "Test setup conflicts with "
                        "confirmed session setup"
                    )
                )

            if resolved_setup_id is None:
                resolved_setup_id = (
                    session.training_setup_id
                )

        setup = None

        if resolved_setup_id is not None:
            setup = TrainingSetupService(
                self.db
            ).get(
                payload.athlete_id,
                resolved_setup_id,
            )

            if setup["sport"] != sport:
                raise ValueError(
                    (
                        "Training setup sport "
                        "does not match test"
                    )
                )

            if (
                setup["environment"]
                != environment
            ):
                raise ValueError(
                    (
                        "Training setup environment "
                        "does not match test"
                    )
                )

            if discipline is None:
                discipline = setup[
                    "discipline"
                ]

            elif (
                setup["discipline"]
                != discipline
            ):
                raise ValueError(
                    (
                        "Training setup discipline "
                        "does not match test"
                    )
                )

        seen_sources: set[
            uuid.UUID
        ] = set()

        devices: dict[
            uuid.UUID,
            Device,
        ] = {}

        allowed_setup_sources: set[
            uuid.UUID
        ] | None = None

        if setup is not None:
            allowed_setup_sources = set()

            for role in (
                "primary_power_source",
                "secondary_power_source",
            ):
                item = setup[
                    "device_roles"
                ].get(role)

                if item is not None:
                    allowed_setup_sources.add(
                        item["id"]
                    )

        for result in payload.results:
            source_id = (
                result.power_source_id
            )

            if source_id in seen_sources:
                raise ValueError(
                    (
                        "Duplicate power source "
                        "in performance test"
                    )
                )

            seen_sources.add(source_id)

            device = self.db.scalar(
                select(Device).where(
                    Device.id == source_id,
                    Device.athlete_id
                    == payload.athlete_id,
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
                    (
                        "Performance test result "
                        "requires a power source"
                    )
                )

            if device.category == "trainer":
                if environment != "indoor":
                    raise ValueError(
                        (
                            "Trainer power observation "
                            "requires indoor environment"
                        )
                    )

                if not bool(
                    device.capabilities.get(
                        "power_measurement"
                    )
                ):
                    raise ValueError(
                        (
                            "Trainer does not expose "
                            "power measurement"
                        )
                    )

            if (
                allowed_setup_sources is not None
                and source_id
                not in allowed_setup_sources
            ):
                raise ValueError(
                    (
                        "Power source is not part "
                        "of linked training setup"
                    )
                )

            devices[source_id] = device

        test = PerformanceTest(
            athlete_id=payload.athlete_id,
            canonical_session_id=
                payload.canonical_session_id,
            training_setup_id=
                resolved_setup_id,
            sport=sport,
            discipline=discipline,
            environment=environment,
            test_type=payload.test_type,
            protocol=
                payload.protocol.strip(),
            tested_at=payload.tested_at,
            protocol_data=
                payload.protocol_data,
            notes=payload.notes,
        )

        self.db.add(test)
        self.db.flush()

        for item in payload.results:
            self.db.add(
                PerformanceTestResult(
                    performance_test_id=
                        test.id,
                    athlete_id=
                        payload.athlete_id,
                    power_source_id=
                        item.power_source_id,
                    observed_power_w=
                        item.observed_power_w,
                    measurement_window_s=
                        item.measurement_window_s,
                    estimated_ftp_w=
                        item.estimated_ftp_w,
                    estimate_method=
                        item.estimate_method,
                    confidence=
                        item.confidence,
                    derivation=
                        item.derivation,
                    metrics=
                        item.metrics,
                    notes=item.notes,
                )
            )

        self.db.commit()
        self.db.refresh(test)

        return self.get(
            athlete_id=
                payload.athlete_id,
            test_id=test.id,
        )

    def get(
        self,
        *,
        athlete_id: uuid.UUID,
        test_id: uuid.UUID,
    ) -> dict:
        test = self.db.scalar(
            select(PerformanceTest).where(
                PerformanceTest.id
                == test_id,
                PerformanceTest.athlete_id
                == athlete_id,
            )
        )

        if test is None:
            raise LookupError(
                "Performance test not found"
            )

        return self._serialize(test)

    def list(
        self,
        *,
        athlete_id: uuid.UUID,
        test_type: str | None = None,
    ) -> list[dict]:
        query = select(
            PerformanceTest
        ).where(
            PerformanceTest.athlete_id
            == athlete_id
        )

        if test_type is not None:
            query = query.where(
                PerformanceTest.test_type
                == test_type
            )

        tests = self.db.scalars(
            query.order_by(
                PerformanceTest.tested_at.desc()
            )
        ).all()

        return [
            self._serialize(test)
            for test in tests
        ]

    def _serialize(
        self,
        test: PerformanceTest,
    ) -> dict:
        rows = self.db.scalars(
            select(
                PerformanceTestResult
            )
            .where(
                PerformanceTestResult
                .performance_test_id
                == test.id
            )
            .order_by(
                PerformanceTestResult
                .created_at.asc()
            )
        ).all()

        setup_roles: dict[
            uuid.UUID,
            str,
        ] = {}

        setup_summary = None

        if test.training_setup_id is not None:
            setup = TrainingSetupService(
                self.db
            ).get(
                test.athlete_id,
                test.training_setup_id,
            )

            setup_summary = {
                "id": setup["id"],
                "name": setup["name"],
            }

            for role in (
                "primary_power_source",
                "secondary_power_source",
            ):
                device = setup[
                    "device_roles"
                ].get(role)

                if device is not None:
                    setup_roles[
                        device["id"]
                    ] = role

        results = []

        for row in rows:
            device = self.db.get(
                Device,
                row.power_source_id,
            )

            results.append(
                {
                    "id": row.id,
                    "power_source_id":
                        row.power_source_id,
                    "power_source": {
                        "id": device.id,
                        "name": device.name,
                        "category":
                            device.category,
                    },
                    "setup_role":
                        setup_roles.get(
                            row.power_source_id
                        ),
                    "observed_power_w":
                        row.observed_power_w,
                    "measurement_window_s":
                        row.measurement_window_s,
                    "estimated_ftp_w":
                        row.estimated_ftp_w,
                    "estimate_method":
                        row.estimate_method,
                    "confidence":
                        row.confidence,
                    "derivation":
                        row.derivation,
                    "metrics":
                        row.metrics,
                    "notes":
                        row.notes,
                }
            )

        return {
            "id": test.id,
            "athlete_id":
                test.athlete_id,
            "canonical_session_id":
                test.canonical_session_id,
            "training_setup_id":
                test.training_setup_id,
            "training_setup":
                setup_summary,
            "sport": test.sport,
            "discipline":
                test.discipline,
            "environment":
                test.environment,
            "test_type":
                test.test_type,
            "protocol":
                test.protocol,
            "tested_at":
                test.tested_at,
            "protocol_data":
                test.protocol_data,
            "notes":
                test.notes,
            "results":
                results,
        }

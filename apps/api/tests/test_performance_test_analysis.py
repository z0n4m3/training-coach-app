from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    User,
    ZoneSet,
)
from app.schemas.cycling_equipment import (
    BikeCreate,
    BikeDeviceAssignmentCreate,
    DeviceCreate,
)
from app.schemas.performance import (
    ZoneSetCreate,
)
from app.schemas.performance_tests import (
    PerformanceTestCreate,
    PerformanceTestResultCreate,
)
from app.schemas.training_setup import (
    TrainingSetupCreate,
)
from app.services.cycling_equipment_service import (
    CyclingEquipmentService,
)
from app.services.performance_profile_service import (
    PerformanceProfileService,
)
from app.services.performance_test_analysis_service import (
    PerformanceTestAnalysisService,
)
from app.services.performance_test_service import (
    PerformanceTestService,
)
from app.services.training_setup_service import (
    TrainingSetupService,
)


def make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    return Session(engine)


def make_fixture(
    db: Session,
):
    user = User(
        timezone="Europe/Warsaw"
    )

    db.add(user)
    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Test Athlete",
    )

    db.add(athlete)
    db.flush()

    equipment = (
        CyclingEquipmentService(db)
    )

    bike = equipment.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Road",
            discipline="road",
        )
    )

    trainer = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Trainer",
            category="trainer",
            mobility="shared",
            capabilities={
                "power_measurement": True,
            },
        )
    )

    power_meter = (
        equipment.create_device(
            DeviceCreate(
                athlete_id=athlete.id,
                name="Bike PM",
                category="power_meter",
                mobility="fixed",
                capabilities={
                    "power_measurement":
                        True,
                },
            )
        )
    )

    equipment.assign_device_to_bike(
        BikeDeviceAssignmentCreate(
            athlete_id=athlete.id,
            bike_id=bike["id"],
            device_id=
                power_meter["id"],
            role="power_source",
        )
    )

    setup = TrainingSetupService(
        db
    ).create(
        TrainingSetupCreate(
            athlete_id=athlete.id,
            name="Road dual power",
            bike_id=bike["id"],
            environment="indoor",
            device_roles={
                "trainer":
                    trainer["id"],
                "primary_power_source":
                    trainer["id"],
                "secondary_power_source":
                    power_meter["id"],
            },
        )
    )

    return (
        athlete,
        setup,
        trainer,
        power_meter,
    )


def record_dual(
    db: Session,
    *,
    athlete,
    setup,
    trainer,
    power_meter,
    tested_at: datetime,
    trainer_w: float,
    power_meter_w: float,
    test_type: str = "calibration",
    protocol: str = "steady_10min",
    window_s: float = 600,
    trainer_ftp: float | None = None,
    power_meter_ftp: float | None = None,
    confidence: str = "medium",
):
    trainer_kwargs = {}

    if trainer_ftp is not None:
        trainer_kwargs = {
            "estimated_ftp_w":
                trainer_ftp,
            "estimate_method":
                "protocol_formula",
            "confidence":
                confidence,
        }

    pm_kwargs = {}

    if power_meter_ftp is not None:
        pm_kwargs = {
            "estimated_ftp_w":
                power_meter_ftp,
            "estimate_method":
                "protocol_formula",
            "confidence":
                confidence,
        }

    return PerformanceTestService(
        db
    ).create(
        PerformanceTestCreate(
            athlete_id=athlete.id,
            environment="indoor",
            test_type=test_type,
            protocol=protocol,
            tested_at=tested_at,
            training_setup_id=
                setup["id"],
            results=[
                PerformanceTestResultCreate(
                    power_source_id=
                        trainer["id"],
                    observed_power_w=
                        trainer_w,
                    measurement_window_s=
                        window_s,
                    **trainer_kwargs,
                ),
                PerformanceTestResultCreate(
                    power_source_id=
                        power_meter["id"],
                    observed_power_w=
                        power_meter_w,
                    measurement_window_s=
                        window_s,
                    **pm_kwargs,
                ),
            ],
        )
    )


def test_source_comparison_uses_only_paired_observations():
    db = make_db()

    (
        athlete,
        setup,
        trainer,
        power_meter,
    ) = make_fixture(db)

    record_dual(
        db,
        athlete=athlete,
        setup=setup,
        trainer=trainer,
        power_meter=power_meter,
        tested_at=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
        trainer_w=242,
        power_meter_w=263,
    )

    result = (
        PerformanceTestAnalysisService(
            db
        ).compare_sources(
            athlete_id=athlete.id,
            source_a_id=
                trainer["id"],
            source_b_id=
                power_meter["id"],
        )
    )

    assert (
        result["paired_tests"]
        == 1
    )

    observation = (
        result["observations"][0]
    )

    assert (
        observation[
            "source_b_minus_a_w"
        ]
        == 21
    )

    assert (
        observation[
            "source_b_vs_a_pct"
        ]
        == 8.678
    )

    group = (
        result[
            "comparison_groups"
        ][0]
    )

    assert (
        group["repeatability"]
        == "insufficient_history"
    )

    assert (
        result["conversion_model"]
        == "none"
    )


def test_three_comparable_pairs_can_show_repeatability():
    db = make_db()

    (
        athlete,
        setup,
        trainer,
        power_meter,
    ) = make_fixture(db)

    observations = [
        (
            datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            242,
            263,
        ),
        (
            datetime(
                2026,
                9,
                15,
                tzinfo=timezone.utc,
            ),
            246,
            267,
        ),
        (
            datetime(
                2026,
                10,
                1,
                tzinfo=timezone.utc,
            ),
            250,
            272,
        ),
    ]

    for (
        tested_at,
        trainer_w,
        pm_w,
    ) in observations:
        record_dual(
            db,
            athlete=athlete,
            setup=setup,
            trainer=trainer,
            power_meter=power_meter,
            tested_at=tested_at,
            trainer_w=trainer_w,
            power_meter_w=pm_w,
        )

    result = (
        PerformanceTestAnalysisService(
            db
        ).compare_sources(
            athlete_id=athlete.id,
            source_a_id=
                trainer["id"],
            source_b_id=
                power_meter["id"],
            environment="indoor",
            discipline="road",
            protocol="steady_10min",
        )
    )

    assert (
        result["paired_tests"]
        == 3
    )

    group = (
        result[
            "comparison_groups"
        ][0]
    )

    assert (
        group["repeatability"]
        == "high"
    )


def test_different_protocols_are_not_collapsed_together():
    db = make_db()

    (
        athlete,
        setup,
        trainer,
        power_meter,
    ) = make_fixture(db)

    record_dual(
        db,
        athlete=athlete,
        setup=setup,
        trainer=trainer,
        power_meter=power_meter,
        tested_at=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
        trainer_w=200,
        power_meter_w=210,
        protocol="steady_10min",
        window_s=600,
    )

    record_dual(
        db,
        athlete=athlete,
        setup=setup,
        trainer=trainer,
        power_meter=power_meter,
        tested_at=datetime(
            2026,
            9,
            2,
            tzinfo=timezone.utc,
        ),
        trainer_w=240,
        power_meter_w=260,
        protocol="ftp_20min",
        window_s=1200,
    )

    result = (
        PerformanceTestAnalysisService(
            db
        ).compare_sources(
            athlete_id=athlete.id,
            source_a_id=
                trainer["id"],
            source_b_id=
                power_meter["id"],
        )
    )

    assert (
        len(
            result[
                "comparison_groups"
            ]
        )
        == 2
    )


def test_ftp_proposal_is_source_specific_and_not_applied():
    db = make_db()

    (
        athlete,
        setup,
        trainer,
        power_meter,
    ) = make_fixture(db)

    PerformanceProfileService(
        db
    ).create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            environment="indoor",
            discipline="road",
            power_source_id=
                trainer["id"],
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=225,
            source="test",
        )
    )

    record_dual(
        db,
        athlete=athlete,
        setup=setup,
        trainer=trainer,
        power_meter=power_meter,
        tested_at=datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        ),
        trainer_w=242,
        power_meter_w=263,
        test_type="ftp",
        protocol="ftp_20min",
        window_s=1200,
        trainer_ftp=230,
        power_meter_ftp=250,
        confidence="high",
    )

    before = list(
        db.scalars(
            select(ZoneSet)
        )
    )

    proposal = (
        PerformanceTestAnalysisService(
            db
        ).ftp_proposal(
            athlete_id=athlete.id,
            power_source_id=
                trainer["id"],
            environment="indoor",
            discipline="road",
            at=datetime(
                2026,
                10,
                5,
                tzinfo=timezone.utc,
            ),
        )
    )

    after = list(
        db.scalars(
            select(ZoneSet)
        )
    )

    assert (
        proposal["status"]
        == "review_required"
    )

    assert (
        proposal["current"][
            "ftp_w"
        ]
        == 225
    )

    assert (
        proposal[
            "proposed_ftp_w"
        ]
        == 230
    )

    assert (
        proposal["delta_w"]
        == 5
    )

    assert (
        proposal["confidence"]
        == "high"
    )

    assert (
        proposal[
            "requires_athlete_approval"
        ]
        is True
    )

    assert (
        proposal["applied"]
        is False
    )

    assert (
        proposal["conversion_used"]
        is False
    )

    assert (
        len(before)
        == len(after)
        == 1
    )


def test_ftp_proposal_does_not_convert_other_source_result():
    db = make_db()

    (
        athlete,
        setup,
        trainer,
        power_meter,
    ) = make_fixture(db)

    record_dual(
        db,
        athlete=athlete,
        setup=setup,
        trainer=trainer,
        power_meter=power_meter,
        tested_at=datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        ),
        trainer_w=242,
        power_meter_w=263,
        test_type="ftp",
        protocol="ftp_20min",
        window_s=1200,
        trainer_ftp=None,
        power_meter_ftp=250,
        confidence="high",
    )

    proposal = (
        PerformanceTestAnalysisService(
            db
        ).ftp_proposal(
            athlete_id=athlete.id,
            power_source_id=
                trainer["id"],
            environment="indoor",
            discipline="road",
            at=datetime(
                2026,
                10,
                5,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert (
        proposal["status"]
        == "insufficient_evidence"
    )

    assert (
        proposal[
            "proposed_ftp_w"
        ]
        is None
    )

    assert (
        proposal["conversion_used"]
        is False
    )

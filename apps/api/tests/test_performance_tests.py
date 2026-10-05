from datetime import (
    datetime,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CanonicalSession,
    PerformanceTest,
    User,
    ZoneSet,
)
from app.schemas.cycling_equipment import (
    BikeCreate,
    BikeDeviceAssignmentCreate,
    DeviceCreate,
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

    session = CanonicalSession(
        athlete_id=athlete.id,
        sport="Ride",
        indoor=True,
        training_setup_id=
            setup["id"],
        start_at=datetime(
            2026,
            9,
            18,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=3600,
        duplicate_status="single",
        analysis_level="basic",
        fingerprint=(
            "dual-power-ftp-test"
        ),
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return (
        athlete,
        setup,
        session,
        trainer,
        power_meter,
    )


def test_multi_source_ftp_test_preserves_observations():
    db = make_db()

    (
        athlete,
        setup,
        session,
        trainer,
        power_meter,
    ) = make_fixture(db)

    result = PerformanceTestService(
        db
    ).create(
        PerformanceTestCreate(
            athlete_id=athlete.id,
            environment="indoor",
            test_type="ftp",
            protocol="ftp_20min",
            tested_at=session.start_at,
            canonical_session_id=
                session.id,
            protocol_data={
                "all_out_window_s":
                    1200,
            },
            results=[
                PerformanceTestResultCreate(
                    power_source_id=
                        trainer["id"],
                    observed_power_w=242,
                    measurement_window_s=
                        1200,
                    estimated_ftp_w=230,
                    estimate_method=
                        "protocol_formula",
                    derivation={
                        "formula":
                            "20min_power_x_0.95",
                        "factor": 0.95,
                    },
                ),
                PerformanceTestResultCreate(
                    power_source_id=
                        power_meter["id"],
                    observed_power_w=263,
                    measurement_window_s=
                        1200,
                    estimated_ftp_w=250,
                    estimate_method=
                        "protocol_formula",
                    derivation={
                        "formula":
                            "20min_power_x_0.95",
                        "factor": 0.95,
                    },
                ),
            ],
        )
    )

    assert (
        result["training_setup_id"]
        == setup["id"]
    )

    assert (
        result["discipline"]
        == "road"
    )

    assert len(
        result["results"]
    ) == 2

    by_source = {
        item["power_source_id"]:
            item
        for item in result["results"]
    }

    assert (
        by_source[
            trainer["id"]
        ]["observed_power_w"]
        == 242
    )

    assert (
        by_source[
            trainer["id"]
        ]["estimated_ftp_w"]
        == 230
    )

    assert (
        by_source[
            trainer["id"]
        ]["setup_role"]
        == "primary_power_source"
    )

    assert (
        by_source[
            power_meter["id"]
        ]["observed_power_w"]
        == 263
    )

    assert (
        by_source[
            power_meter["id"]
        ]["estimated_ftp_w"]
        == 250
    )

    assert (
        by_source[
            power_meter["id"]
        ]["setup_role"]
        == "secondary_power_source"
    )

    # M6E1 stores observations only.
    # It must not invent a permanent
    # device conversion ratio.
    assert (
        "conversion_ratio"
        not in result
    )

    for item in result["results"]:
        assert (
            "conversion_ratio"
            not in item
        )

    # A recorded test is evidence,
    # not automatic FTP approval.
    zone_sets = list(
        db.scalars(
            select(ZoneSet)
        )
    )

    assert zone_sets == []


def test_duplicate_power_source_is_rejected():
    db = make_db()

    (
        athlete,
        _,
        session,
        trainer,
        _,
    ) = make_fixture(db)

    with pytest.raises(
        ValueError,
        match="Duplicate power source",
    ):
        PerformanceTestService(
            db
        ).create(
            PerformanceTestCreate(
                athlete_id=athlete.id,
                environment="indoor",
                test_type="ftp",
                protocol="ftp_20min",
                tested_at=
                    session.start_at,
                canonical_session_id=
                    session.id,
                results=[
                    PerformanceTestResultCreate(
                        power_source_id=
                            trainer["id"],
                        observed_power_w=
                            242,
                    ),
                    PerformanceTestResultCreate(
                        power_source_id=
                            trainer["id"],
                        observed_power_w=
                            243,
                    ),
                ],
            )
        )


def test_trainer_observation_cannot_be_outdoor():
    db = make_db()

    (
        athlete,
        _,
        _,
        trainer,
        _,
    ) = make_fixture(db)

    with pytest.raises(
        ValueError,
        match="indoor environment",
    ):
        PerformanceTestService(
            db
        ).create(
            PerformanceTestCreate(
                athlete_id=athlete.id,
                discipline="road",
                environment="outdoor",
                test_type="calibration",
                protocol="steady_power",
                tested_at=datetime(
                    2026,
                    9,
                    20,
                    tzinfo=timezone.utc,
                ),
                results=[
                    PerformanceTestResultCreate(
                        power_source_id=
                            trainer["id"],
                        observed_power_w=
                            200,
                    )
                ],
            )
        )


def test_linked_setup_rejects_unknown_power_source():
    db = make_db()

    (
        athlete,
        setup,
        session,
        _,
        _,
    ) = make_fixture(db)

    equipment = (
        CyclingEquipmentService(db)
    )

    other_source = (
        equipment.create_device(
            DeviceCreate(
                athlete_id=athlete.id,
                name="Other PM",
                category="power_meter",
                mobility="movable",
                capabilities={
                    "power_measurement":
                        True,
                },
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="not part of linked",
    ):
        PerformanceTestService(
            db
        ).create(
            PerformanceTestCreate(
                athlete_id=athlete.id,
                environment="indoor",
                test_type="ftp",
                protocol="ftp_20min",
                tested_at=
                    session.start_at,
                training_setup_id=
                    setup["id"],
                results=[
                    PerformanceTestResultCreate(
                        power_source_id=
                            other_source["id"],
                        observed_power_w=
                            250,
                    )
                ],
            )
        )


def test_test_record_is_persisted_as_one_event():
    db = make_db()

    (
        athlete,
        _,
        session,
        trainer,
        power_meter,
    ) = make_fixture(db)

    service = PerformanceTestService(
        db
    )

    created = service.create(
        PerformanceTestCreate(
            athlete_id=athlete.id,
            environment="indoor",
            test_type="calibration",
            protocol="dual_recording",
            tested_at=session.start_at,
            canonical_session_id=
                session.id,
            results=[
                PerformanceTestResultCreate(
                    power_source_id=
                        trainer["id"],
                    observed_power_w=200,
                    measurement_window_s=
                        600,
                ),
                PerformanceTestResultCreate(
                    power_source_id=
                        power_meter["id"],
                    observed_power_w=210,
                    measurement_window_s=
                        600,
                ),
            ],
        )
    )

    tests = list(
        db.scalars(
            select(PerformanceTest)
        )
    )

    assert len(tests) == 1

    loaded = service.get(
        athlete_id=athlete.id,
        test_id=created["id"],
    )

    assert (
        len(loaded["results"])
        == 2
    )

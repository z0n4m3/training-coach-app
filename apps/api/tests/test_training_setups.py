from sqlalchemy import (
    create_engine,
    event,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    User,
)
from app.schemas.cycling_equipment import (
    BikeCreate,
    BikeDeviceAssignmentCreate,
    DeviceCreate,
)
from app.schemas.training_setup import (
    TrainingSetupCreate,
)
from app.services.cycling_equipment_service import (
    CyclingEquipmentService,
)
from app.services.training_setup_service import (
    TrainingSetupService,
)


def make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    @event.listens_for(
        engine,
        "connect",
    )
    def _fk_on(
        dbapi_connection,
        connection_record,
    ):
        cursor = (
            dbapi_connection.cursor()
        )
        cursor.execute(
            "PRAGMA foreign_keys=ON"
        )
        cursor.close()

    Base.metadata.create_all(
        engine
    )

    return Session(engine)


def make_athlete(
    db: Session,
) -> Athlete:
    user = User(
        timezone="Europe/Warsaw"
    )

    db.add(user)
    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Test",
    )

    db.add(athlete)
    db.commit()

    return athlete


def setup_inventory(
    db: Session,
):
    athlete = make_athlete(db)

    equipment = (
        CyclingEquipmentService(db)
    )

    road = equipment.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Road",
            discipline="road",
        )
    )

    gravel = equipment.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Gravel",
            discipline="gravel",
        )
    )

    road_pm = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Road PM",
            category="power_meter",
            mobility="fixed",
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
                "resistance_control": True,
            },
        )
    )

    hr = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="HR strap",
            category=
                "heart_rate_sensor",
            mobility="shared",
        )
    )

    edge = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Bike computer",
            category=
                "recording_device",
            mobility="shared",
        )
    )

    core = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="CORE",
            category=
                "temperature_sensor",
            mobility="shared",
        )
    )

    equipment.assign_device_to_bike(
        BikeDeviceAssignmentCreate(
            athlete_id=athlete.id,
            bike_id=road["id"],
            device_id=road_pm["id"],
            role="power_source",
        )
    )

    return {
        "athlete": athlete,
        "road": road,
        "gravel": gravel,
        "road_pm": road_pm,
        "trainer": trainer,
        "hr": hr,
        "edge": edge,
        "core": core,
    }


def test_outdoor_setup_is_explicit():
    db = make_db()
    items = setup_inventory(db)

    setup = TrainingSetupService(
        db
    ).create(
        TrainingSetupCreate(
            athlete_id=
                items["athlete"].id,
            name="Road outdoor",
            bike_id=
                items["road"]["id"],
            environment="outdoor",
            device_roles={
                "primary_power_source":
                    items["road_pm"]["id"],
                "hr_source":
                    items["hr"]["id"],
                "recording_device":
                    items["edge"]["id"],
                "temperature_source":
                    items["core"]["id"],
            },
        )
    )

    assert (
        setup["discipline"]
        == "road"
    )

    assert (
        setup["environment"]
        == "outdoor"
    )

    assert (
        setup["device_roles"]
        ["primary_power_source"]
        ["name"]
        == "Road PM"
    )


def test_indoor_setup_supports_two_power_sources():
    db = make_db()
    items = setup_inventory(db)

    setup = TrainingSetupService(
        db
    ).create(
        TrainingSetupCreate(
            athlete_id=
                items["athlete"].id,
            name=(
                "Road indoor "
                "trainer primary"
            ),
            bike_id=
                items["road"]["id"],
            environment="indoor",
            device_roles={
                "trainer":
                    items["trainer"]["id"],
                "primary_power_source":
                    items["trainer"]["id"],
                "secondary_power_source":
                    items["road_pm"]["id"],
                "hr_source":
                    items["hr"]["id"],
            },
        )
    )

    assert (
        setup["device_roles"]
        ["primary_power_source"]
        ["name"]
        == "Trainer"
    )

    assert (
        setup["device_roles"]
        ["secondary_power_source"]
        ["name"]
        == "Road PM"
    )


def test_power_meter_must_belong_to_selected_bike():
    db = make_db()
    items = setup_inventory(db)

    try:
        TrainingSetupService(
            db
        ).create(
            TrainingSetupCreate(
                athlete_id=
                    items["athlete"].id,
                name="Invalid gravel",
                bike_id=
                    items["gravel"]["id"],
                environment="outdoor",
                device_roles={
                    "primary_power_source":
                        items["road_pm"]["id"],
                },
            )
        )

    except ValueError as exc:
        assert (
            "not assigned"
            in str(exc)
        )

    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_outdoor_setup_cannot_use_trainer():
    db = make_db()
    items = setup_inventory(db)

    try:
        TrainingSetupService(
            db
        ).create(
            TrainingSetupCreate(
                athlete_id=
                    items["athlete"].id,
                name="Invalid outdoor",
                bike_id=
                    items["road"]["id"],
                environment="outdoor",
                device_roles={
                    "trainer":
                        items["trainer"]["id"],
                },
            )
        )

    except ValueError as exc:
        assert "Outdoor" in str(exc)

    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_trainer_power_requires_measurement_capability():
    db = make_db()
    items = setup_inventory(db)

    equipment = (
        CyclingEquipmentService(db)
    )

    basic_trainer = (
        equipment.create_device(
            DeviceCreate(
                athlete_id=
                    items["athlete"].id,
                name="Basic trainer",
                category="trainer",
                mobility="shared",
                capabilities={
                    "power_measurement":
                        False,
                },
            )
        )
    )

    try:
        TrainingSetupService(
            db
        ).create(
            TrainingSetupCreate(
                athlete_id=
                    items["athlete"].id,
                name="Invalid trainer power",
                bike_id=
                    items["road"]["id"],
                environment="indoor",
                device_roles={
                    "trainer":
                        basic_trainer["id"],
                    "primary_power_source":
                        basic_trainer["id"],
                },
            )
        )

    except ValueError as exc:
        assert (
            "power_measurement"
            in str(exc)
        )

    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_secondary_power_requires_primary():
    db = make_db()
    items = setup_inventory(db)

    try:
        TrainingSetupService(
            db
        ).create(
            TrainingSetupCreate(
                athlete_id=
                    items["athlete"].id,
                name="Invalid secondary",
                bike_id=
                    items["road"]["id"],
                environment="indoor",
                device_roles={
                    "secondary_power_source":
                        items["road_pm"]["id"],
                },
            )
        )

    except ValueError as exc:
        assert (
            "requires primary"
            in str(exc)
        )

    else:
        raise AssertionError(
            "Expected ValueError"
        )

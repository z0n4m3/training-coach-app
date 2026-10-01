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
from app.services.cycling_equipment_service import (
    CyclingEquipmentService,
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

    Base.metadata.create_all(engine)

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


def test_power_meter_can_belong_to_only_one_bike_when_fixed():
    db = make_db()
    athlete = make_athlete(db)
    service = CyclingEquipmentService(db)

    road = service.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Road",
            discipline="road",
        )
    )

    gravel = service.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Gravel",
            discipline="gravel",
        )
    )

    pm = service.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Road power meter",
            category="power_meter",
            mobility="fixed",
        )
    )

    service.assign_device_to_bike(
        BikeDeviceAssignmentCreate(
            athlete_id=athlete.id,
            bike_id=road["id"],
            device_id=pm["id"],
            role="power_source",
        )
    )

    try:
        service.assign_device_to_bike(
            BikeDeviceAssignmentCreate(
                athlete_id=athlete.id,
                bike_id=gravel["id"],
                device_id=pm["id"],
                role="power_source",
            )
        )
    except ValueError as exc:
        assert "another bike" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_movable_power_meter_can_be_available_on_two_bikes():
    db = make_db()
    athlete = make_athlete(db)
    service = CyclingEquipmentService(db)

    road = service.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Road",
            discipline="road",
        )
    )

    gravel = service.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Gravel",
            discipline="gravel",
        )
    )

    pm = service.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Movable PM",
            category="power_meter",
            mobility="movable",
        )
    )

    for bike in (road, gravel):
        service.assign_device_to_bike(
            BikeDeviceAssignmentCreate(
                athlete_id=athlete.id,
                bike_id=bike["id"],
                device_id=pm["id"],
                role="power_source",
            )
        )

    inventory = service.inventory(
        athlete.id
    )

    counts = {
        bike["name"]:
            len(
                bike[
                    "device_assignments"
                ]
            )
        for bike in inventory["bikes"]
    }

    assert counts["Road"] == 1
    assert counts["Gravel"] == 1


def test_shared_equipment_is_not_assumed_to_belong_to_bike():
    db = make_db()
    athlete = make_athlete(db)
    service = CyclingEquipmentService(db)

    for name, category in (
        (
            "HR strap",
            "heart_rate_sensor",
        ),
        (
            "Edge",
            "recording_device",
        ),
        (
            "CORE",
            "temperature_sensor",
        ),
    ):
        service.create_device(
            DeviceCreate(
                athlete_id=athlete.id,
                name=name,
                category=category,
                mobility="shared",
            )
        )

    inventory = service.inventory(
        athlete.id
    )

    names = {
        device["name"]
        for device
        in inventory["shared_devices"]
    }

    assert names == {
        "HR strap",
        "Edge",
        "CORE",
    }


def test_trainer_function_is_stored_without_requiring_model():
    db = make_db()
    athlete = make_athlete(db)
    service = CyclingEquipmentService(db)

    trainer = service.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Home trainer",
            category="trainer",
            mobility="shared",
            capabilities={
                "power_measurement": True,
                "resistance_control": True,
                "erg_mode": True,
            },
        )
    )

    assert trainer["category"] == "trainer"
    assert (
        trainer["capabilities"][
            "power_measurement"
        ]
        is True
    )

    assert trainer["details"] == {}


def test_manufacturer_and_model_can_be_optional_metadata():
    db = make_db()
    athlete = make_athlete(db)
    service = CyclingEquipmentService(db)

    trainer = service.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Trainer",
            category="trainer",
            mobility="shared",
            capabilities={
                "power_measurement": True,
            },
            details={
                "manufacturer": "Elite",
                "model": "Suito",
            },
        )
    )

    assert (
        trainer["details"]["manufacturer"]
        == "Elite"
    )

    assert (
        trainer["details"]["model"]
        == "Suito"
    )


def test_hr_sensor_cannot_be_bike_power_source():
    db = make_db()
    athlete = make_athlete(db)
    service = CyclingEquipmentService(db)

    bike = service.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Road",
            discipline="road",
        )
    )

    hr = service.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="HR",
            category="heart_rate_sensor",
            mobility="shared",
        )
    )

    try:
        service.assign_device_to_bike(
            BikeDeviceAssignmentCreate(
                athlete_id=athlete.id,
                bike_id=bike["id"],
                device_id=hr["id"],
                role="power_source",
            )
        )
    except ValueError as exc:
        assert "cannot be used" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError"
        )

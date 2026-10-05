from datetime import datetime, timezone

import pytest
from sqlalchemy import (
    create_engine,
    event,
    select,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    SportProfile,
    User,
    ZoneSet,
)
from app.schemas.performance import ZoneSetCreate
from app.services.performance_profile_service import (
    PerformanceProfileService,
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


def create_zone(
    service: PerformanceProfileService,
    athlete_id,
    *,
    context: str,
    effective_from: datetime,
    ftp_w: float,
    sport: str = "cycling",
):
    return service.create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete_id,
            sport=sport,
            context=context,
            effective_from=effective_from,
            ftp_w=ftp_w,
            source="test",
        )
    )


def test_indoor_and_outdoor_ftp_are_separate():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    effective = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    indoor = create_zone(
        service,
        athlete.id,
        context="indoor",
        effective_from=effective,
        ftp_w=230,
    )

    outdoor = create_zone(
        service,
        athlete.id,
        context="outdoor",
        effective_from=effective,
        ftp_w=250,
    )

    assert indoor["ftp_w"] == 230
    assert outdoor["ftp_w"] == 250

    profiles = list(
        db.scalars(
            select(SportProfile)
        )
    )

    assert len(profiles) == 2


def test_effective_zone_set_is_versioned_by_date():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    create_zone(
        service,
        athlete.id,
        context="outdoor",
        effective_from=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
        ftp_w=250,
        sport="Ride",
    )

    create_zone(
        service,
        athlete.id,
        context="outdoor",
        effective_from=datetime(
            2026,
            10,
            15,
            tzinfo=timezone.utc,
        ),
        ftp_w=255,
    )

    october_first = (
        service.effective_zone_set(
            athlete_id=athlete.id,
            sport="cycling",
            context="outdoor",
            at=datetime(
                2026,
                10,
                1,
                tzinfo=timezone.utc,
            ),
        )
    )

    november_first = (
        service.effective_zone_set(
            athlete_id=athlete.id,
            sport="Ride",
            context="outdoor",
            at=datetime(
                2026,
                11,
                1,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert october_first is not None
    assert october_first["ftp_w"] == 250

    assert november_first is not None
    assert november_first["ftp_w"] == 255


def test_new_version_does_not_overwrite_history():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    create_zone(
        service,
        athlete.id,
        context="indoor",
        effective_from=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
        ftp_w=225,
    )

    create_zone(
        service,
        athlete.id,
        context="indoor",
        effective_from=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
        ftp_w=230,
    )

    rows = list(
        db.scalars(
            select(ZoneSet).order_by(
                ZoneSet.effective_from.asc()
            )
        )
    )

    assert len(rows) == 2
    assert rows[0].ftp_w == 225
    assert rows[1].ftp_w == 230


def test_duplicate_effective_date_is_rejected():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    effective = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    create_zone(
        service,
        athlete.id,
        context="outdoor",
        effective_from=effective,
        ftp_w=250,
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        create_zone(
            service,
            athlete.id,
            context="outdoor",
            effective_from=effective,
            ftp_w=255,
        )


def test_no_future_zone_set_is_used_for_old_session():
    db = make_db()
    athlete = make_athlete(db)

    service = PerformanceProfileService(
        db
    )

    create_zone(
        service,
        athlete.id,
        context="outdoor",
        effective_from=datetime(
            2026,
            10,
            15,
            tzinfo=timezone.utc,
        ),
        ftp_w=255,
    )

    result = service.effective_zone_set(
        athlete_id=athlete.id,
        sport="cycling",
        context="outdoor",
        at=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result is None


def make_power_sources(
    db: Session,
    athlete: Athlete,
):
    from app.schemas.cycling_equipment import (
        DeviceCreate,
    )
    from app.services.cycling_equipment_service import (
        CyclingEquipmentService,
    )

    equipment = CyclingEquipmentService(
        db
    )

    trainer = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Trainer power",
            category="trainer",
            mobility="shared",
            capabilities={
                "power_measurement": True,
            },
        )
    )

    power_meter = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Bike power meter",
            category="power_meter",
            mobility="movable",
            capabilities={
                "power_measurement": True,
            },
        )
    )

    return trainer, power_meter


def test_same_environment_can_have_separate_power_sources():
    db = make_db()
    athlete = make_athlete(db)

    trainer, power_meter = (
        make_power_sources(
            db,
            athlete,
        )
    )

    service = PerformanceProfileService(
        db
    )

    effective = datetime(
        2026,
        9,
        18,
        tzinfo=timezone.utc,
    )

    trainer_zone = (
        service.create_zone_set(
            ZoneSetCreate(
                athlete_id=athlete.id,
                sport="cycling",
                environment="indoor",
                discipline="road",
                power_source_id=
                    trainer["id"],
                effective_from=effective,
                ftp_w=230,
                source="test",
            )
        )
    )

    meter_zone = (
        service.create_zone_set(
            ZoneSetCreate(
                athlete_id=athlete.id,
                sport="cycling",
                environment="indoor",
                discipline="road",
                power_source_id=
                    power_meter["id"],
                effective_from=effective,
                ftp_w=253,
                source="test",
            )
        )
    )

    assert trainer_zone["ftp_w"] == 230
    assert meter_zone["ftp_w"] == 253

    assert (
        trainer_zone["power_source_id"]
        == trainer["id"]
    )
    assert (
        meter_zone["power_source_id"]
        == power_meter["id"]
    )

    assert (
        trainer_zone["profile_key"]
        != meter_zone["profile_key"]
    )


def test_effective_profile_is_resolved_by_power_source():
    db = make_db()
    athlete = make_athlete(db)

    trainer, power_meter = (
        make_power_sources(
            db,
            athlete,
        )
    )

    service = PerformanceProfileService(
        db
    )

    effective = datetime(
        2026,
        9,
        18,
        tzinfo=timezone.utc,
    )

    for source_id, ftp in (
        (trainer["id"], 230),
        (power_meter["id"], 253),
    ):
        service.create_zone_set(
            ZoneSetCreate(
                athlete_id=athlete.id,
                environment="indoor",
                discipline="road",
                power_source_id=source_id,
                effective_from=effective,
                ftp_w=ftp,
                source="test",
            )
        )

    trainer_result = (
        service.effective_zone_set(
            athlete_id=athlete.id,
            sport="cycling",
            environment="indoor",
            discipline="road",
            power_source_id=
                trainer["id"],
            at=datetime(
                2026,
                10,
                1,
                tzinfo=timezone.utc,
            ),
        )
    )

    meter_result = (
        service.effective_zone_set(
            athlete_id=athlete.id,
            sport="cycling",
            environment="indoor",
            discipline="road",
            power_source_id=
                power_meter["id"],
            at=datetime(
                2026,
                10,
                1,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert trainer_result is not None
    assert meter_result is not None

    assert trainer_result["ftp_w"] == 230
    assert meter_result["ftp_w"] == 253


def test_source_specific_profile_cannot_bind_hr():
    db = make_db()
    athlete = make_athlete(db)

    trainer, _ = make_power_sources(
        db,
        athlete,
    )

    with pytest.raises(
        ValueError,
        match="HR metrics",
    ):
        ZoneSetCreate(
            athlete_id=athlete.id,
            environment="indoor",
            discipline="road",
            power_source_id=
                trainer["id"],
            effective_from=datetime(
                2026,
                9,
                18,
                tzinfo=timezone.utc,
            ),
            ftp_w=230,
            threshold_hr_bpm=178,
            source="test",
        )


def test_trainer_power_profile_cannot_be_outdoor():
    db = make_db()
    athlete = make_athlete(db)

    trainer, _ = make_power_sources(
        db,
        athlete,
    )

    service = PerformanceProfileService(
        db
    )

    with pytest.raises(
        ValueError,
        match="indoor environment",
    ):
        service.create_zone_set(
            ZoneSetCreate(
                athlete_id=athlete.id,
                environment="outdoor",
                discipline="road",
                power_source_id=
                    trainer["id"],
                effective_from=datetime(
                    2026,
                    9,
                    18,
                    tzinfo=timezone.utc,
                ),
                ftp_w=230,
                source="test",
            )
        )
